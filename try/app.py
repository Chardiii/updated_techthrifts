from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from mysql.connector import Error
from werkzeug.utils import secure_filename
import os,json



app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for flash messages and session management

UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


    
def save_image(image_file):
    """Save the uploaded image file to the server and return the filename."""
    if image_file and allowed_file(image_file.filename):
        filename = secure_filename(image_file.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(image_path)
        return filename
    return None

def allowed_file(filename):
    """Check if the uploaded file is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
# MySQL Database connection
def get_db_connection():
    conn = mysql.connector.connect(
        host='localhost',  # Your MySQL host, default is 'localhost'
        user='root',  # Your MySQL username
        password='',  # Your MySQL password
        database='ecomdb'  # The database you want to connect to
    )
    return conn
def get_product_by_id(product_id):
    """Fetch a product from the database by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute('SELECT * FROM products WHERE id = %s', (product_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    return product
# Route to display the homepage
@app.route('/')
def homepage():
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute('SELECT * FROM products WHERE seller_id IS NOT NULL')
    seller_products = cursor.fetchall()
    
    cursor.execute('SELECT * FROM products WHERE flash_sale = TRUE')
    flash_sale_products = cursor.fetchall()

    return render_template('homepage.html', seller_products=seller_products, flash_sale_products=flash_sale_products)
    

# Route to display the registration page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        email = request.form['email']
        password = request.form['password']
        role = 'user'  # Default role is 'customer'

        # Establish a database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Check if the email already exists
            cursor.execute('SELECT COUNT(*) FROM users WHERE email = %s', (email,))
            email_exists = cursor.fetchone()[0] > 0

            if email_exists:
                flash('This email is already registered. Please use a different email.', 'warning')
                return render_template('register.html')

            # Insert the user data into the MySQL database
            cursor.execute(
                '''INSERT INTO users (email, password, role) 
                VALUES (%s, %s, %s)''', (email, password, role)
            )
            conn.commit()

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))

        except mysql.connector.Error as err:
            flash(f"Error: {err}", 'danger')

        finally:
            conn.close()

    return render_template('register.html')


# Route to display the login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        conn.close()
        
        # Start the session
        session['logged_in'] = True
        
        if user and user[2] == password:  # user[2] is the password
            
            session['user_id'] = user[0]  # user[0] is the user_id
            session['role'] = user[3]  # user[3] is the role
            session['email'] = user[1]  # user[1] is the email
            session['username'] = user[1].split('@')[0]  # Extract username from email (before @)

            flash('Login successful!', 'success')

            role = user[3]

            # Redirect based on the user's role
            if role == 'superadmin':
                return redirect(url_for('superadmin_dashboard'))
            elif role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif role == 'seller':
                return redirect(url_for('homepage'))
            else:
                return redirect(url_for('homepage'))

        else:
            flash('Invalid email or password', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


# Route to handle logout functionality
@app.route('/logout')
def logout():
    session.pop('logged_in', None)  # Removes 'logged_in' from session
    session.pop('user_id', None)  # Removes 'user_id' if you have it
    flash('You have been logged out.', 'info')  # Optional, for user feedback
    return redirect(url_for('login'))  # Redirect to login page
# Admin route
@app.route('/admin_dashboard')
def admin_dashboard():
    # Connect to the database
    connection = get_db_connection()

    # Create a cursor to execute SQL queries
    cursor = connection.cursor()

    # Query to get the number of users by counting the user id
    cursor.execute("SELECT COUNT(id) AS total_users FROM users")
    users_result = cursor.fetchone()
    total_users = users_result[0]

    # Query to get the number of products by counting the product id
    cursor.execute("SELECT COUNT(id) as total_products FROM products")
    products_result = cursor.fetchone()
    total_products = products_result[0]

    # Close the connection
    cursor.close()
    connection.close()

    # Pass the data to the template
    return render_template('admin_dashboard.html', total_users=total_users, total_products=total_products)

# Superadmin route
@app.route('/superadmin_dashboard')
def superadmin_dashboard():
    return render_template('superadmin_dashboard.html')

@app.route('/sellerhomepage')
def sellerhomepage():
    if session.get('role') != 'seller':
        return redirect(url_for('homepage'))  # Redirect non-sellers to homepage

    # Handle search query and redirect to product page
    search_query = request.args.get('search_query', '').strip()
    if search_query:
        return redirect(url_for('products', search_query=search_query))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch all products for the seller
        cursor.execute('SELECT * FROM products WHERE seller_id = %s', (session['user_id'],))
        seller_products = cursor.fetchall()

        # Fetch all products marked as flash sale
        cursor.execute('SELECT * FROM products WHERE flash_sale = TRUE')
        flash_sale_products = cursor.fetchall()
        
    finally:
        cursor.close()
        conn.close()

    return render_template('sellerhomepage.html', seller_products=seller_products, flash_sale_products=flash_sale_products)



@app.route('/product', methods=['GET'])
def product():
    search_query = request.args.get('search_query', '').strip()  # Get the search query from the request
    sort_option = request.args.get('sort', 'name_asc')  # Default sort is 'name_asc'
   
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Initialize base query for filtering products by seller_id
        base_query = '''
            SELECT * FROM products 
            WHERE seller_id IS NOT NULL
        '''

        # Add search query condition if a search query exists
        if search_query:
            search_query = f"%{search_query}%"  # This allows partial matching with LIKE
            base_query += " AND name LIKE %s"
            cursor.execute(base_query, (search_query,))
        else:
            cursor.execute(base_query)

        # Fetch all results to avoid unread result error
        seller_products = cursor.fetchall()
        clean_search_query = search_query.replace('%', '')
    finally:
        cursor.close()  # Now safe to close cursor after all results are fetched
        conn.close()

    # Render the template with the products, search query, and sort option
    return render_template('product.html', seller_products=seller_products, search_query=search_query, sort_option=sort_option)


@app.route('/product/sort', methods=['GET'])
def sort_product():
    search_query = request.args.get('search_query', '').strip()  # Get the search query from the request
    sort_option = request.args.get('sort', 'name_asc')  # Default sort is 'name_asc'
   
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Initialize base query for filtering products by seller_id
        base_query = '''
            SELECT * FROM products 
            WHERE seller_id IS NOT NULL
        '''
        
        # Add search query condition if a search query exists
        if search_query:
            search_query = f"%{search_query}%"  # This allows partial matching with LIKE
            base_query += " AND name LIKE %s"
        clean_search_query = search_query.replace('%', '')
        # Add sorting based on the selected sort option
        if sort_option == 'name_asc':
            base_query += " ORDER BY name ASC"
        elif sort_option == 'name_desc':
            base_query += " ORDER BY name DESC"
        elif sort_option == 'price_asc':
            base_query += " ORDER BY price ASC"
        elif sort_option == 'price_desc':
            base_query += " ORDER BY price DESC"
        elif sort_option == 'stock_asc':
            base_query += " ORDER BY stock ASC"
        elif sort_option == 'stock_desc':
            base_query += " ORDER BY stock DESC"

        # Execute the final query with the parameters if there is a search query
        if search_query:
            cursor.execute(base_query, (search_query,))
        else:
            cursor.execute(base_query)
      
        # Fetch all results to avoid unread result error
        seller_products = cursor.fetchall()
        

    finally:
        cursor.close()  # Now safe to close cursor after all results are fetched
        conn.close()

    # Render the template with the products, search query, and sort option
    return render_template('product.html', seller_products=seller_products, search_query=search_query, sort_option=sort_option)

    

# Seller registration route
@app.route('/seller-registration', methods=['GET', 'POST'])
def seller_registration():
    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        email = request.form['email']  # Remove leading/trailing spaces
        phonenumber = request.form['phonenumber']
        address = request.form['address']
        businessname = request.form['businessname']
        description = request.form['description']

        # Debugging: Print out the email and check for existing users
        
        conn = get_db_connection()
        cursor = conn.cursor()

        
       

        

        try:
            query = """
                INSERT INTO sellers (firstname, lastname, email, phonenumber, address, businessname, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            values = (firstname, lastname, email, phonenumber, address, businessname, description)
            cursor.execute(query, values)
            conn.commit()

            flash('Seller registered successfully!', 'success')
            return redirect('/seller-registration')

        except mysql.connector.Error as err:
            flash(f"Error registering seller: {err}", 'danger')
            print(f"Error: {err}")  # Log the error for debugging

        finally:
            cursor.close()
            conn.close()

    return render_template('seller_registration.html')



# Route to manage sellers
@app.route('/manage_sellers')
def manage_sellers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sellers = []

    try:
        cursor.execute("""
            SELECT sellerid, firstname, lastname, email, phonenumber, address, businessname, description, createdtime, status
            FROM sellers
        """)
        sellers = cursor.fetchall()

    except Exception as e:
        print(f"Error fetching sellers data: {e}")
        sellers = []

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template('manage_sellers.html', sellers=sellers)


# Route to approve seller
@app.route('/approve_seller/<int:sellerid>', methods=['POST'])
def approve_seller(sellerid):
    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("SELECT email FROM sellers WHERE sellerid = %s", (sellerid,))
        seller = cursor.fetchone()

        if seller is None:
            flash("Seller not found.", category="danger")
            return redirect(url_for('manage_sellers'))

        email = seller[0]

        query = "UPDATE sellers SET status = 'Approved' WHERE sellerid = %s"
        cursor.execute(query, (sellerid,))

        cursor.execute("UPDATE users SET role = %s WHERE email = %s", ('seller', email))

        conn.commit()

        flash("Seller approved successfully and role updated!", category="success")
        return redirect(url_for('manage_sellers'))

    except Error as e:
        flash(f"Error: {e}", category="danger")
        return redirect(url_for('manage_sellers'))

    finally:
        if conn:
            conn.close()

# Route to decline seller
@app.route('/decline_seller/<int:sellerid>', methods=['POST'])
def decline_seller(sellerid):
    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("SELECT email FROM sellers WHERE sellerid = %s", (sellerid,))
        seller = cursor.fetchone()

        if seller is None:
            flash("Seller not found.", category="danger")
            return redirect(url_for('manage_sellers'))

        email = seller[0]

        query = "UPDATE sellers SET status = 'Declined' WHERE sellerid = %s"
        cursor.execute(query, (sellerid,))

        cursor.execute("UPDATE users SET role = %s WHERE email = %s", ('user', email))

        conn.commit()

        flash("Seller approved successfully and role updated!", category="success")
        return redirect(url_for('manage_sellers'))

    except Error as e:
        flash(f"Error: {e}", category="danger")
        return redirect(url_for('manage_sellers'))

    finally:
        if conn:
            conn.close()
            
#add products

@app.route('/add_product', methods=['POST'])
def add_product():
    product_name = request.form['product_name']
    product_description = request.form['product_description']
    product_price = request.form['product_price']
    product_stock = request.form['product_stock']
    product_category = request.form['product_category']
    product_color = request.form['product_color']
    product_image = request.files['product_image']

    discount_type = request.form.get('discount_type')
    discount_value = request.form.get('product_discount', type=float)
    coupon_code = request.form.get('coupon_code')

    flash_sale = request.form.get('flash_sale') == 'on'

    if product_image and allowed_file(product_image.filename):
        filename = secure_filename(product_image.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        product_image.save(image_path)

        # Removed additional images handling

        # Database insertion logic
        user_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO products (name, description, price, stock, image, category, seller_id, color, discount_type, discount_value, coupon_code, flash_sale)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (product_name, product_description, product_price, product_stock, filename, product_category, user_id, product_color, discount_type, discount_value, coupon_code, flash_sale))
            conn.commit()
            flash('Product added successfully!', 'success')
        except mysql.connector.Error as e:
            conn.rollback()
            flash(f'An error occurred while adding the product: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()
    else:
        flash('Invalid image file. Please upload a valid image (png, jpg, jpeg, gif).', 'error')

    return redirect(url_for('sellerhomepage'))


@app.route('/sellerdashboard', methods=['GET'])
def sellerdashboard():
    user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    page = request.args.get('page', 1, type=int)
    limit = 15
    offset = (page - 1) * limit

    cursor.execute('SELECT * FROM products WHERE seller_id = %s LIMIT %s OFFSET %s', (user_id, limit, offset))
    seller_products = cursor.fetchall()

    cursor.execute('SELECT * FROM products WHERE seller_id = %s', (user_id,))
    seller_products = cursor.fetchall()

    cursor.execute('SELECT COUNT(*) as total FROM products WHERE seller_id = %s', (user_id,))
    total_products = cursor.fetchone()['total']
    total_pages = (total_products + limit - 1) // limit 

    # Modified query to join 'orders' with 'users' to get user email
    cursor.execute('''
        SELECT o.id AS order_id, oi.quantity, oi.price, o.total_price, o.status AS order_status, o.created_at, 
               p.name AS product_name, u.email AS user_email
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id 
        JOIN products p ON oi.product_id = p.id
        JOIN users u ON o.user_id = u.id  -- Join with the 'users' table to get user email
        WHERE p.seller_id = %s
    ''', (user_id,))
    orders = cursor.fetchall()

    total_sales = sum(order['quantity'] for order in orders)
    total_revenue = sum(order['total_price'] for order in orders)

    cursor.execute('''
        SELECT o.id AS order_id, o.total_price, o.created_at 
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id 
        JOIN products p ON oi.product_id = p.id 
        WHERE p.seller_id = %s
        ORDER BY o.created_at DESC
        LIMIT 5
    ''', (user_id,))
    recent_orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('sellerdashboard.html',  
                           seller_products=seller_products, 
                           orders=orders, 
                           total_sales=total_sales, 
                           total_revenue=total_revenue, 
                           recent_orders=recent_orders, 
                           page=page, 
                           total_pages=total_pages)



@app.route('/productmanagement')
def productmanagement():
    return render_template('productmanagement.html')


#product details
@app.route('/products', methods=['GET'])
def product_listing():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute('SELECT * FROM products')
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('productdetails.html', products=products)

@app.route('/product/<int:product_id>', methods=['GET', 'POST'])
def product_details(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    app.jinja_env.globals['json'] = json

    try:
        # Retrieve product details from the database
        cursor.execute('SELECT * FROM products WHERE id = %s', (product_id,))
        product = cursor.fetchone()

        if product:
            # Check if the user is logged in
            user_id = session.get('user_id')
            has_purchased = False

            if user_id:
                # Check if the user has purchased the product
                cursor.execute("""
                    SELECT COUNT(*) AS count
                    FROM order_items oi
                    JOIN orders o ON oi.order_id = o.id
                    WHERE o.user_id = %s AND oi.product_id = %s
                """, (user_id, product_id))
                has_purchased = cursor.fetchone()['count'] > 0

            if request.method == 'POST':
                if not user_id:
                    flash('You must be logged in to leave a review.', 'error')
                    return redirect(url_for('login'))

                if not has_purchased:
                    flash('You can only review products you have purchased.', 'error')
                    return redirect(url_for('product_details', product_id=product_id))

                # Get the rating and comment from the form
                rating = request.form['rating']
                comment = request.form['comment']

                # Insert the new review into the database
                cursor.execute("""
                    INSERT INTO reviews (product_id, user_id, rating, comment)
                    VALUES (%s, %s, %s, %s)
                """, (product_id, user_id, rating, comment))
                conn.commit()

                flash('Review submitted successfully!', 'success')

            # Retrieve the reviews for the product
            cursor.execute("""
                SELECT r.rating, r.comment, r.created_at, u.email AS username 
                FROM reviews r
                JOIN users u ON r.user_id = u.id
                WHERE r.product_id = %s
                ORDER BY r.created_at DESC
            """, (product_id,))
            reviews = cursor.fetchall()

            # Render the product details page with reviews and purchase status
            return render_template(
                'productdetails.html',
                product=product,
                reviews=reviews,
                has_purchased=has_purchased
            )

        else:
            flash('Product not found.', 'error')
            return redirect(url_for('homepage'))

    except mysql.connector.Error as e:
        flash('An error occurred while retrieving product details.', 'error')
        print(f"Database error: {e}") 
        return redirect(url_for('homepage'))

    finally:
        cursor.close()
        conn.close()
        
@app.route('/laptop')
def laptop():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute('SELECT * FROM products WHERE category = "Laptop"')
    seller_products = cursor.fetchall()
    
    return render_template('laptop.html', seller_products=seller_products)

@app.route('/cellphone')
def cellphone():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute('SELECT * FROM products WHERE category = "Cellphone"')
    seller_products = cursor.fetchall()
    
    return render_template('cellphone.html', seller_products=seller_products)  

@app.route('/camera')
def camera():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute('SELECT * FROM products WHERE category = "Camera"')
    seller_products = cursor.fetchall()
    
    return render_template('camera.html', seller_products=seller_products)     

@app.route('/inventorymanagement')
def inventorymanagement():
    # Ensure the user is logged in and is a seller
    if 'user_id' not in session or session.get('role') != 'seller':
        return redirect(url_for('login'))  # Redirect to login if not a seller

    # Get the logged-in user's ID
    user_id = session.get('user_id')

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch only the products belonging to the logged-in seller (i.e., match the seller_id)
    cursor.execute('SELECT * FROM products WHERE seller_id = %s', (user_id,))
    seller_products = cursor.fetchall()

    return render_template('inventorymanagement.html', seller_products=seller_products)


@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    product = get_product_by_id(product_id)
    if request.method == 'POST':
        product['name'] = request.form['product_name']
        product['description'] = request.form['product_description']
        product['price'] = float(request.form['product_price'])
        product['stock'] = int(request.form['product_stock'])
        product['category'] = (request.form['product_category'])
        product['color'] = request.form['product_color']
        product['discount_value'] = float(request.form['product_discount']) if request.form['product_discount'] else None
        product['discount_type'] = request.form['discount_type']
        

        if 'product_image' in request.files:
            file = request.files['product_image']
            new_image_filename = save_image(file)
            if new_image_filename:
                product['image'] = new_image_filename

        update_product_in_db(product) 
        flash('Product updated successfully!', 'success')
        return redirect(url_for('product_details', product_id=product['id']))

    return render_template('edit_product.html', product=product)

  
@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if the product exists before trying to delete
        cursor.execute('SELECT * FROM products WHERE id = %s', (product_id,))
        product = cursor.fetchone()

        if product is None:
            flash('Product not found.', 'error')
            return redirect(url_for('sellerdashboard'))

        # Delete the product
        cursor.execute('DELETE FROM products WHERE id = %s', (product_id,))
        conn.commit()
        flash('Product deleted successfully!', 'success')

        # Optionally, you can log notifications or other actions here
    except Exception as e:
        conn.rollback()
        flash(f'An error occurred while deleting the product: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('sellerdashboard'))

def update_product_in_db(product):
    """Update the product in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE products 
        SET name = %s, description = %s, price = %s, stock = %s, category = %s, color = %s,
            discount_value = %s, discount_type = %s, coupon_code = %s, image = %s
        WHERE id = %s
    ''', (product['name'], product['description'], product['price'], product['stock'],
          product['category'], product['color'], product['discount_value'], 
          product['discount_type'], product['coupon_code'], product['image'], product['id']))

    conn.commit()
    cursor.close()
    conn.close()


#add to cart 
# Route for adding products to the cart
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))
    print(f"Received product_id: {product_id}, quantity: {quantity}")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check if product exists
    cursor.execute('SELECT * FROM products WHERE id = %s', (product_id,))
    product = cursor.fetchone()
    if not product:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Product not found'}), 404

    # Check if enough stock is available
    if product['stock'] < quantity:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Not enough stock available'}), 400

    # Check if user is logged in
    user_id = session.get('user_id')
    if not user_id:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': 'User not logged in'}), 401

    # Check if the user already has a cart
    cursor.execute('SELECT id FROM carts WHERE user_id = %s', (user_id,))
    cart = cursor.fetchone()

    if not cart:
        # Create a new cart for the user
        cursor.execute('INSERT INTO carts (user_id) VALUES (%s)', (user_id,))
        conn.commit()
        cart_id = cursor.lastrowid
    else:
        cart_id = cart['id']

    # Check if the product is already in the cart
    cursor.execute('SELECT quantity FROM cart_items WHERE cart_id = %s AND product_id = %s', (cart_id, product_id))
    cart_item = cursor.fetchone()

    if cart_item:
        # Update quantity if it exists
        new_quantity = cart_item['quantity'] + quantity
        cursor.execute('UPDATE cart_items SET quantity = %s WHERE cart_id = %s AND product_id = %s', (new_quantity, cart_id, product_id))
    else:
        # Add a new item to the cart
        cursor.execute('INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (%s, %s, %s)', (cart_id, product_id, quantity))

    # Reduce the product's stock
    cursor.execute('UPDATE products SET stock = stock - %s WHERE id = %s', (quantity, product_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'redirect': url_for('view_cart')})


#cart
@app.route('/cart', methods=['GET'])
def view_cart():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))  # Redirect to login if user is not logged in

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Query to fetch cart items with image and subtotal
    cursor.execute('''
        SELECT 
            ci.product_id, 
            ci.quantity, 
            p.name AS product_name, 
            p.price, 
            (ci.quantity * p.price) AS subtotal, 
            p.image
        FROM cart_items ci
        JOIN products p ON ci.product_id = p.id
        JOIN carts c ON ci.cart_id = c.id
        WHERE c.user_id = %s
    ''', (user_id,))
    
    cart_items = cursor.fetchall()

    cursor.close()
    conn.close()

    total_price = sum(item['subtotal'] for item in cart_items)

    return render_template('cart.html', cart_items=cart_items, total_price=total_price)


@app.route('/update_cart_quantity', methods=['POST'])
def update_cart_quantity():
    data = request.get_json()
    product_id = data.get('product_id')
    change = int(data.get('change', 0))

    if not product_id or not change:
        return jsonify({'success': False, 'error': 'Invalid request data'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    user_id = session.get('user_id')
    if not user_id:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': 'User not logged in'}), 401

    # Fetch cart and product stock
    cursor.execute('''
        SELECT ci.quantity AS cart_quantity, p.stock AS product_stock 
        FROM cart_items ci 
        JOIN carts c ON ci.cart_id = c.id 
        JOIN products p ON ci.product_id = p.id 
        WHERE c.user_id = %s AND ci.product_id = %s
    ''', (user_id, product_id))
    item = cursor.fetchone()

    if not item:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Item not found in cart'}), 404

    new_quantity = item['cart_quantity'] + change
    new_stock = item['product_stock'] - change

    if new_stock < 0:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Insufficient stock'}), 400

    if new_quantity <= 0:
        # Remove item from cart if quantity becomes 0
        cursor.execute('''
            DELETE FROM cart_items 
            WHERE product_id = %s AND cart_id = (SELECT id FROM carts WHERE user_id = %s)
        ''', (product_id, user_id))
    else:
        # Update cart item quantity
        cursor.execute('''
            UPDATE cart_items 
            SET quantity = %s 
            WHERE product_id = %s AND cart_id = (SELECT id FROM carts WHERE user_id = %s)
        ''', (new_quantity, product_id, user_id))

    # Update product stock
    cursor.execute('''
        UPDATE products 
        SET stock = %s 
        WHERE id = %s
    ''', (new_stock, product_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'new_quantity': max(new_quantity, 0), 'new_stock': new_stock})


@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    data = request.get_json()
    product_id = data.get('product_id')
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({'success': False, 'error': 'User not logged in'}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Find cart ID for the user
    cursor.execute('SELECT id FROM carts WHERE user_id = %s', (user_id,))
    cart = cursor.fetchone()

    if not cart:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Cart not found'}), 404

    cart_id = cart['id']

    # Find the cart item and its quantity
    cursor.execute('SELECT quantity FROM cart_items WHERE cart_id = %s AND product_id = %s', (cart_id, product_id))
    cart_item = cursor.fetchone()

    if not cart_item:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Product not in cart'}), 404

    # Restore stock
    cursor.execute('UPDATE products SET stock = stock + %s WHERE id = %s', (cart_item['quantity'], product_id))

    # Remove the item from the cart
    cursor.execute('DELETE FROM cart_items WHERE cart_id = %s AND product_id = %s', (cart_id, product_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'redirect': url_for('view_cart')})

#profile
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user_id = session.get('user_id')  # Get logged-in user's ID from session
    if not user_id:
        # If no user is logged in, redirect to the login page
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # Use dictionary=True for readability

    if request.method == 'POST':
        # Retrieve the form values
        birthday = request.form.get('birthday')
        address = request.form.get('address')
        gender = request.form.get('gender')
        new_email = request.form.get('new_email')

        # Update email if provided
        if new_email:
            cursor.execute("""
                UPDATE users
                SET email = %s
                WHERE id = %s
            """, (new_email, user_id))

        # Update other profile information (birthday, address, gender)
        cursor.execute("""
            UPDATE users
            SET birthday = %s, address = %s, gender = %s
            WHERE id = %s
        """, (birthday, address, gender, user_id))

        # Handle password update (if provided)
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_new_password')

        if current_password and new_password and confirm_password:
            cursor.execute("SELECT password FROM users WHERE id = %s", (user_id,))
            user_data = cursor.fetchone()

            if user_data:  # Check if a row is returned
                db_password = user_data['password']  # Accessing the 'password' column directly by key
                if db_password == current_password:  # Direct comparison (plain text)
                    if new_password == confirm_password:
                        cursor.execute("""
                            UPDATE users
                            SET password = %s
                            WHERE id = %s
                        """, (new_password, user_id))
                        flash('Password updated successfully!', 'success')
                    else:
                        flash('New passwords do not match!', 'error')
                else:
                    flash('Current password is incorrect.', 'error')
            else:
                flash('User not found or no password available.', 'error')

        conn.commit()
        flash('Profile updated successfully!', 'success')

    # Retrieve the user data from the database
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if user:
        username = user['email'].split('@')[0]  # Extract username from email
        email = user['email']
        birthday = user['birthday']
        address = user['address']
        gender = user['gender']

        # Query to get the orders for the logged-in user
        cursor.execute("""
            SELECT 
                o.id AS order_id, 
                o.status, 
                oi.quantity,
                oi.price,
                p.name AS product_name
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE o.user_id = %s
            ORDER BY o.created_at DESC
        """, (user_id,))

        orders = cursor.fetchall()

        order_details = []
        for order in orders:
            order_details.append({
                'order_id': order['order_id'],
                'status': order['status'],
                'product_name': order['product_name'],
                'quantity': order['quantity'],
                'price': order['price'],
            })

        return render_template(
            'profile.html', 
            username=username, 
            email=email, 
            birthday=birthday, 
            address=address, 
            gender=gender, 
            orders=order_details
        )
    
    flash('User not found', 'error')
    return redirect(url_for('login'))



@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in to checkout', 'error')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if request.method == 'POST':
            shipping_address = request.form['shipping_address']
            payment_method = request.form['payment_method']

            # Get cart items and cart ID
            cursor.execute('''
                SELECT c.id as cart_id, p.id as product_id, p.name, p.price, ci.quantity
                FROM cart_items ci
                JOIN carts c ON ci.cart_id = c.id
                JOIN products p ON ci.product_id = p.id
                WHERE c.user_id = %s
            ''', (user_id,))
            cart_items = cursor.fetchall()

            if not cart_items:
                flash('Your cart is empty', 'error')
                return redirect(url_for('view_cart'))

            # Calculate total price
            total_amount = sum(item['price'] * item['quantity'] for item in cart_items)

            # Create order
            cursor.execute('''
                INSERT INTO orders (user_id, total_price, status, shipping_address, payment_method, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            ''', (user_id, total_amount, 'Pending', shipping_address, payment_method))
            
            order_id = cursor.lastrowid

            # Create order items
            for item in cart_items:
                cursor.execute('''
                    INSERT INTO order_items (order_id, product_id, quantity, price)
                    VALUES (%s, %s, %s, %s)
                ''', (order_id, item['product_id'], item['quantity'], item['price']))

            # Clear cart items
            cart_id = cart_items[0]['cart_id']
            cursor.execute('DELETE FROM cart_items WHERE cart_id = %s', (cart_id,))

            conn.commit()
            flash('Order placed successfully!', 'success')
            return redirect(url_for('homepage'))

        # GET request - show checkout page
        cursor.execute('''
            SELECT p.id, p.name, p.price, ci.quantity
            FROM cart_items ci
            JOIN carts c ON ci.cart_id = c.id
            JOIN products p ON ci.product_id = p.id
            WHERE c.user_id = %s
        ''', (user_id,))
        
        cart_items = cursor.fetchall()
        total_price = sum(item['price'] * item['quantity'] for item in cart_items)

        return render_template('checkout.html', cart=cart_items, total_price=total_price)

    except Exception as e:
        print(f"Error during checkout: {e}")
        conn.rollback()
        flash('An error occurred during checkout. Please try again.', 'error')
        return redirect(url_for('view_cart'))

    finally:
        cursor.close()
        conn.close()

@app.route('/cancel_checkout', methods=['GET'])
def cancel_checkout():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in to cancel checkout', 'error')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Retrieve the pending order for this user
        cursor.execute('''
            SELECT oi.product_id, oi.quantity, c.id AS cart_id
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            LEFT JOIN carts c ON c.user_id = o.user_id
            WHERE o.user_id = %s AND o.status = %s
        ''', (user_id, 'Pending'))
        order_items = cursor.fetchall()

        if not order_items:
            flash('No pending orders to cancel.', 'error')
            return redirect(url_for('view_cart'))

        # Restore items to the cart
        for item in order_items:
            # Check if the product is already in the cart
            cursor.execute('''
                SELECT id, quantity
                FROM cart_items
                WHERE cart_id = %s AND product_id = %s
            ''', (item['cart_id'], item['product_id']))
            cart_item = cursor.fetchone()

            if cart_item:
                # Update the quantity if it exists
                new_quantity = cart_item['quantity'] + item['quantity']
                cursor.execute('''
                    UPDATE cart_items
                    SET quantity = %s
                    WHERE id = %s
                ''', (new_quantity, cart_item['id']))
            else:
                # Insert a new cart item
                cursor.execute('''
                    INSERT INTO cart_items (cart_id, product_id, quantity)
                    VALUES (%s, %s, %s)
                ''', (item['cart_id'], item['product_id'], item['quantity']))

        # Delete the pending order and its items
        cursor.execute('''
            DELETE FROM order_items
            WHERE order_id IN (
                SELECT id FROM orders
                WHERE user_id = %s AND status = %s
            )
        ''', (user_id, 'Pending'))
        cursor.execute('''
            DELETE FROM orders
            WHERE user_id = %s AND status = %s
        ''', (user_id, 'Pending'))

        conn.commit()
        flash('Checkout cancelled and items returned to your cart.', 'success')
        return redirect(url_for('view_cart'))

    except Exception as e:
        print(f"Error during checkout cancellation: {e}")
        conn.rollback()
        flash('An error occurred while cancelling checkout. Please try again.', 'error')
        return redirect(url_for('view_cart'))

    finally:
        cursor.close()
        conn.close()


@app.route('/salemanagement/orders', methods=['GET', 'POST'])
def salemanagement():
    # Ensure the user is logged in as a seller
    if 'role' not in session or session['role'] != 'seller':
        flash('Please log in as a seller to view your orders.', 'error')
        return redirect(url_for('login'))

    # Get the seller's user ID from the session
    user_id = session['user_id']
    
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Query to get all orders that contain the seller's products
    cursor.execute("""
        SELECT 
            o.id AS order_id, 
            o.user_id AS buyer_id, 
            o.total_price, 
            o.status, 
            o.shipping_address, 
            o.payment_method, 
            o.created_at,
            u.email AS buyer_name,  # Using email for the buyer's name
            oi.product_id,
            oi.quantity,
            p.name AS product_name
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        JOIN users u ON o.user_id = u.id  # Getting buyer's email
        WHERE p.seller_id = %s  -- This links the seller (owner of the product)
        ORDER BY o.created_at DESC
    """, (user_id,))
    
    raw_orders = cursor.fetchall()

    # Process orders to group by order_id and product
    processed_orders = {}
    for item in raw_orders:
        order_id = item['order_id']
        
        if order_id not in processed_orders:
            processed_orders[order_id] = {
                'order_id': order_id,
                'buyer_name': item['buyer_name'],  # Using email as buyer's name
                'total_price': item['total_price'],
                'status': item['status'],
                'shipping_address': item['shipping_address'],
                'payment_method': item['payment_method'],
                'created_at': item['created_at'],
                'products': []
            }

        product = {
            'product_name': item['product_name'],
            'quantity': item['quantity'],
            'product_id': item['product_id']
        }

        processed_orders[order_id]['products'].append(product)
    
    # Convert to list format for template
    orders = list(processed_orders.values())

    connection.close()
    return render_template('salemanagement.html', orders=orders)



@app.route('/salemanagement/orders/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    # Ensure the user is logged in as a seller
    if 'role' not in session or session['role'] != 'seller':
        flash('Please log in as a seller to update the order status.', 'error')
        return redirect(url_for('login'))

    # Get the new status from the form
    new_status = request.form.get('status')
    
    if new_status:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Update the order status in the database
        cursor.execute("""
            UPDATE orders
            SET status = %s
            WHERE id = %s
        """, (new_status, order_id))
        
        connection.commit()
        connection.close()
        
        flash('Order status updated successfully!', 'success')

    return redirect(url_for('salemanagement'))
@app.route('/mark_as_received/<int:order_id>', methods=['POST'])
def mark_as_received(order_id):
    user_id = session.get('user_id')  # Get logged-in user's ID from session
    if not user_id:
        # If no user is logged in, redirect to the login page
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if the order belongs to the logged-in user
    cursor.execute("""
        SELECT o.status
        FROM orders o
        WHERE o.id = %s AND o.user_id = %s
    """, (order_id, user_id))
    order = cursor.fetchone()

    if order:
        # If the order is found, update its status to "Received" (or any desired status)
        if order['status'] not in ['Delivered', 'Cancelled']:  # Only allow if order is not already delivered or cancelled
            cursor.execute("""
                UPDATE orders
                SET status = 'Received'
                WHERE id = %s AND user_id = %s
            """, (order_id, user_id))

            conn.commit()
            return jsonify({"message": "Order successfully marked as received!"}), 200
        else:
            return jsonify({"message": "Order is already delivered or cancelled, cannot mark as received."}), 400
    else:
        return jsonify({"message": "Order not found or not owned by the user."}), 404



@app.route('/search', methods=['POST'])
def search_products():
    # Get the search query from the form
    name = request.form.get('name')

    # Establish a database connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Query to search products by name
    query = "SELECT * FROM products WHERE name LIKE %s"
    cursor.execute(query, ('%' + name + '%',))  # Use wildcards for partial matching

    # Fetch the search results
    products = cursor.fetchall()

    # Close the database connection
    cursor.close()
    conn.close()

    # Render the product search results
    return render_template('product_search_results.html', products=products)

# Route to display the products page (if needed)
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)