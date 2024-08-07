import app.database as database
import json
import re
from openai import OpenAI
from os import environ as env
from urllib.parse import quote_plus, urlencode
from app.helpers import login_required
from authlib.integrations.flask_client import OAuth
from ..extensions import oauth
from flask import Flask, request, session, url_for, redirect, jsonify, flash, current_app, g, render_template
# from flask_login import login_required, login_user, current_user
from . import base


@base.route('/')
# @login_required
def index():
    db = database.get_db()
    cursor = db.cursor(dictionary=True)

    query = " SELECT InventoryItems.*, Locations.location_name FROM InventoryItems JOIN Locations ON InventoryItems.location_id = Locations.location_id;"

    cursor.execute(query)
    inventory = cursor.fetchall()
    cursor.close()
    return render_template('index.html', inventory=inventory)

@base.route('/assistant')
def assistant():
    return render_template('assistant.html')

@base.route('/send_message', methods=['POST'])
def send_message():
    client = OpenAI(api_key=env.get("OPENAI_API_KEY"))
    data = request.json
    user_message = data['message']
    thread_id = data.get('threadId')

    if not thread_id:
        thread = client.beta.threads.create()
        thread_id = thread.id
    else:
        thread = client.beta.threads.retrieve(thread_id)

    # Add user message to thread
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message,
    )

    # Run the thread
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=env.get("OPENAI_ASSISTANT_ID"),
    )

    if run.status == "failed":
        return jsonify({"error": f"Run failed: {run.last_error}"}), 500

    # Retrieve the messages in the thread and get the most recent response
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    new_response = messages.data[0].content[0].text.value

    # Use re.sub() to remove the matched source tags from the API response
    # pattern = r'【\d+†source】'
    # cleaned_response = re.sub(pattern, '', new_response)
    # Remove the source tags and trailing newlines
    cleaned_response = re.sub(r'【\d+[:†]\d+†source】', '', new_response)
    cleaned_response = cleaned_response.strip()
    print(cleaned_response)

    return jsonify({"response": cleaned_response, "threadId": thread_id})



@base.route('/removeitem', methods=['POST'])
def remove_item():
    item_id = request.form['item_id']
    print(item_id)

    db = database.get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM InventoryItems WHERE inventory_item_id= %s", (item_id,))
    db.commit()
    cursor.close()
    return redirect("/")

@base.route('/createitem', methods=['POST'])
def create_item():
    # Ensure name was submitted
    if not request.form.get("itemName"):
        return "must give a name"

    item_name = request.form['itemName']
    item_description = request.form['itemDescription']
    item_location = request.form['itemLocation']
    item_GTIN = request.form['itemGTIN']
    item_SKU = request.form['itemSKU']
    item_unit = request.form['itemUnit']
    item_weight = request.form['itemWeight'] if request.form['itemWeight'] else None
    item_price = request.form['itemPrice'] if request.form['itemPrice'] else None
    item_stock = request.form['itemStock'] if request.form['itemStock'] else None
    item_low_stock_level = request.form['itemLowStockLevel'] if request.form['itemLowStockLevel'] else None

    db = database.get_db()
    cursor = db.cursor()
    # Execute the SQL query to insert a new item
    insert_query = """
    INSERT INTO InventoryItems (name, description, location_id, GTIN, SKU, unit, weight, price, stock, low_stock_level)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(insert_query, (item_name, item_description, 1, item_GTIN, item_SKU, item_unit, item_weight, item_price, item_stock, item_low_stock_level))

    db.commit()
    cursor.close()

    return redirect("/")

@base.route('/updateitem', methods=['POST'])
def update_item():
    # Ensure name was entered!
    if not request.form.get("editItemName"):
        return "Item name is required."

    # collect a
    item_id = request.form['editItemID']
    print(item_id)
    item_name = request.form['editItemName']
    item_description = request.form['editItemDescription']
    print(item_description)
    item_location = request.form['editItemLocation']
    item_GTIN = request.form['editItemGTIN']
    item_SKU = request.form['editItemSKU']
    item_unit = request.form['editItemUnit']
    item_weight = request.form['editItemWeight'] if request.form['editItemWeight'] else None
    item_price = request.form['editItemPrice'] if request.form['editItemPrice'] else None
    item_stock = request.form['editItemStock'] if request.form['editItemStock'] else None
    item_low_stock_threshold = request.form['editItemLowStockLevel'] if request.form['editItemLowStockLevel'] else None

    db = database.get_db()
    cursor = db.cursor()

    # Execute the SQL query to update the item
    update_query = """
    UPDATE InventoryItems
    SET name = %s,
        description = %s,
        location_id = %s,
        GTIN = %s,
        SKU = %s,
        unit = %s,
        weight = %s,
        price = %s,
        stock = %s,
        low_stock_level = %s
    WHERE inventory_item_id = %s
    """
    cursor.execute(update_query, (item_name, item_description, item_location, item_GTIN, item_SKU, item_unit, item_weight, item_price, item_stock, item_low_stock_threshold, item_id))
    
    db.commit()
    cursor.close()

    return redirect("/")

@base.route('/get_item_details', methods=['POST'])
def get_item_details():
    item_id = request.form.get('editItemId')
    print(item_id)
    db = database.get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM InventoryItems WHERE InventoryItems.inventory_item_id = %s", (item_id,))
    item_details = cursor.fetchone()
    cursor.close()
    
    return jsonify(item_details)

@base.route('/restricted')
@login_required
def restricted_page():
    return 'test'        

# Controllers API
@base.route("/test")
def home():
    return json.dumps(session.get("user"), indent=4)


@base.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token
    return redirect("/")


@base.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("base.callback", _external=True)
    )


@base.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://"
        + env.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("index", _external=True),
                "client_id": env.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )

@base.route("/temp")
def temp():
    return render_template("datatable.html")
    # return render_template('index.html')
