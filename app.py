import os
import requests
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'super_secret_hackathon_key')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# --- DEBUG LOGGING FOR VERCEL ---
if not SUPABASE_URL:
    print("❌ ERROR: SUPABASE_URL is missing from environment!")
else:
    print(f"✅ SUPABASE_URL is active: {SUPABASE_URL[:15]}...")

if not SUPABASE_KEY:
    print("❌ ERROR: SUPABASE_KEY is missing from environment!")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# --- HELPERS ---
def login_required(role=None):
    if 'user_id' not in session:
        return False
    if role and session.get('role').lower() != role.lower():
        return False
    return True

@app.route('/')
def index():
    # Phase 1: Root Role Selector
    return render_template('index.html')

# --- CONTEXTUAL AUTH ROUTES ---

@app.route('/<role>/signup', methods=['GET', 'POST'])
def role_signup(role):
    # role will be 'user', 'creator', or 'admin'
    if role not in ['user', 'creator', 'admin']:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not email or not password:
            return render_template('signup_contextual.html', role=role, error="All fields are required.")
        
        if password != confirm_password:
            return render_template('signup_contextual.html', role=role, error="Passwords do not match.")

        hashed_pw = generate_password_hash(password)
        
        try:
            data = {
                "email": email,
                "password_hash": hashed_pw,
                "role": role
            }
            response = requests.post(f"{SUPABASE_URL}/rest/v1/users", headers=HEADERS, json=data)
            
            if response.status_code in [200, 201]:
                return redirect(url_for('role_login', role=role))
            else:
                error_data = response.json() if response.text else {"message": "Unknown Error"}
                error_msg = error_data.get('message', response.text)
                return render_template('signup_contextual.html', role=role, error=f"Signup Failed: {error_msg}")
        except Exception as e:
            return render_template('signup_contextual.html', role=role, error=f"System Error: {e}")

    return render_template('signup_contextual.html', role=role)

@app.route('/<role>/login', methods=['GET', 'POST'])
def role_login(role):
    if role not in ['user', 'creator', 'admin']:
        return redirect(url_for('index'))

    error = request.args.get('error')
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            api_url = f"{SUPABASE_URL}/rest/v1/users?email=eq.{email}"
            response = requests.get(api_url, headers=HEADERS)
            
            if response.status_code != 200:
                error_data = response.json() if response.text else {"message": "Unauthorized or Database Error"}
                return render_template('login_contextual.html', role=role, error=f"Login Error: {error_data.get('message', 'Check your API Key')}")

            user_data = response.json()

            if user_data:
                user = user_data[0]
                if check_password_hash(user['password_hash'], password) and user['role'].lower() == role.lower():
                    session['user_id'] = user['id']
                    session['email'] = user['email']
                    session['role'] = role
                    
                    if role == 'admin':
                        return redirect(url_for('admin_dashboard'))
                    elif role == 'creator':
                        return redirect(url_for('creator_dashboard'))
                    else:
                        return redirect(url_for('user_dashboard'))
                else:
                    return render_template('login_contextual.html', role=role, error="Invalid password or role.")
            else:
                return render_template('login_contextual.html', role=role, error="User not found.")
        except Exception as e:
            return render_template('login_contextual.html', role=role, error=f"Login Error: {e}")

    return render_template('login_contextual.html', role=role, error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- USER (CONTENT VIEWER) DASHBOARD ---

# --- PAYOUT CALCULATION LOGIC ---
def calculate_dynamic_payout(unique_views, likes, comments):
    """
    Calculates payout based on Unique Views and Engagement Ratio.
    Engagement Ratio = (Likes + Comments) / Unique Views
    """
    if unique_views == 0:
        return 0.0
    
    engagement_ratio = (likes + comments) / unique_views
    # Indian Rupee Formula: ₹10.00 per unique view, boosted by engagement ratio
    base_rate = 10.00 
    engagement_boost = 1 + min(engagement_ratio, 1.0)
    
    payout = unique_views * base_rate * engagement_boost
    return "{:,.2f}".format(payout) # Format with commas for INR

@app.route('/user/dashboard')
def user_dashboard():
    if not login_required(role='user'):
        return redirect(url_for('role_login', role='user', error="Unauthorized access."))
    
    user_id = session.get('user_id')
    try:
        response = requests.get(f"{SUPABASE_URL}/rest/v1/content?select=*,users(email)", headers=HEADERS)
        content_list = response.json()
        
        for item in content_list:
            item['date'] = item.get('created_at', 'Today')[:10]
            item['creator_name'] = item.get('users', {}).get('email', 'Unknown Creator')
            
            # --- VIEW TRACKING LOGIC ---
            # 1. Always increment Total Views
            new_total = (item.get('total_views') or 0) + 1
            requests.patch(f"{SUPABASE_URL}/rest/v1/content?id=eq.{item['id']}", headers=HEADERS, json={"total_views": new_total})
            
            # 2. Check for Unique View
            view_check = requests.get(f"{SUPABASE_URL}/rest/v1/views?user_id=eq.{user_id}&content_id=eq.{item['id']}", headers=HEADERS).json()
            if not view_check:
                # First time seeing this!
                requests.post(f"{SUPABASE_URL}/rest/v1/views", headers=HEADERS, json={"user_id": user_id, "content_id": item['id']})
                new_unique = (item.get('unique_views') or 0) + 1
                requests.patch(f"{SUPABASE_URL}/rest/v1/content?id=eq.{item['id']}", headers=HEADERS, json={"unique_views": new_unique})
                # Update local item for immediate display
                item['unique_views'] = new_unique
            else:
                item['unique_views'] = item.get('unique_views', 0)

            # Fetch likes/comments counts
            likes_res = requests.get(f"{SUPABASE_URL}/rest/v1/likes?content_id=eq.{item['id']}&select=count", headers=HEADERS)
            item['likes'] = likes_res.json()[0]['count'] if likes_res.status_code == 200 else 0
            comm_res = requests.get(f"{SUPABASE_URL}/rest/v1/comments?content_id=eq.{item['id']}&select=count", headers=HEADERS)
            item['comments'] = comm_res.json()[0]['count'] if comm_res.status_code == 200 else 0
            
        return render_template('user_dashboard.html', email=session.get('email'), content=content_list)
    except Exception as e:
        print(f"Error in user dashboard: {e}")
        return render_template('user_dashboard.html', email=session.get('email'), content=[])

# --- INTERACTION API ENDPOINTS ---

@app.route('/api/user/like_content', methods=['POST'])
def like_content():
    if not login_required(role='user'):
        return jsonify({"error": "Unauthorized"}), 403
    
    content_id = request.json.get('content_id')
    user_id = session.get('user_id')
    
    try:
        data = {"user_id": user_id, "content_id": content_id}
        response = requests.post(f"{SUPABASE_URL}/rest/v1/likes", headers=HEADERS, json=data)
        
        # Increment like count in content table (simplified for demo)
        # In real app: supabase.rpc('increment_likes', {'content_id': content_id})
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/user/add_comment', methods=['POST'])
def add_comment():
    if not login_required(role='user'):
        return jsonify({"error": "Unauthorized"}), 403
    
    content_id = request.json.get('content_id')
    body = request.json.get('body')
    user_id = session.get('user_id')
    
    try:
        data = {"user_id": user_id, "content_id": content_id, "body": body}
        requests.post(f"{SUPABASE_URL}/rest/v1/comments", headers=HEADERS, json=data)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- EXISTING DASHBOARD ROUTES ---

@app.route('/admin_dashboard')
def admin_dashboard():
    if not login_required(role='admin'):
        return redirect(url_for('role_login', role='admin', error="Unauthorized access."))
    
    try:
        # Fetch all creators and their aggregated stats
        response = requests.get(f"{SUPABASE_URL}/rest/v1/users?role=eq.creator", headers=HEADERS)
        creators_list = response.json()
        
        display_creators = []
        for c in creators_list:
            content_res = requests.get(f"{SUPABASE_URL}/rest/v1/content?creator_id=eq.{c['id']}", headers=HEADERS).json()
            uv = sum(item.get('unique_views', 0) for item in content_res)
            rv = sum(item.get('total_views', 0) for item in content_res)
            
            # Fetch interaction counts
            total_likes = 0
            total_comments = 0
            for item in content_res:
                l = requests.get(f"{SUPABASE_URL}/rest/v1/likes?content_id=eq.{item['id']}&select=count", headers=HEADERS).json()[0]['count']
                c_comm = requests.get(f"{SUPABASE_URL}/rest/v1/comments?content_id=eq.{item['id']}&select=count", headers=HEADERS).json()[0]['count']
                total_likes += l
                total_comments += c_comm

            ratio = round(rv / uv, 1) if uv > 0 else 1.0
            payout = calculate_dynamic_payout(uv, total_likes, total_comments)
            
            suspicion = "Low"
            if ratio > 2.0: suspicion = "Medium"
            if ratio > 4.0: suspicion = "High 🚩"
            
            display_creators.append({
                "name": c.get('email').split('@')[0],
                "raw_views": rv,
                "unique_views": uv,
                "suspicion": suspicion,
                "payout": f"₹{payout}"
            })
            
        return render_template('admin_dashboard.html', creators=display_creators)
    except Exception as e:
        print(f"Admin Dashboard Error: {e}")
        return render_template('admin_dashboard.html', creators=[])

@app.route('/creator_dashboard')
def creator_dashboard():
    if not login_required(role='creator'):
        return redirect(url_for('role_login', role='creator', error="Unauthorized access."))
    return render_template('creator_dashboard.html', email=session.get('email'))

@app.route('/creator/overview')
def creator_overview():
    if not login_required(role='creator'):
        return redirect(url_for('role_login', role='creator', error="Unauthorized access."))
    
    try:
        api_url = f"{SUPABASE_URL}/rest/v1/content?creator_id=eq.{session['user_id']}"
        response = requests.get(api_url, headers=HEADERS)
        real_content = response.json()
        
        total_unique_views = 0
        total_raw_views = 0
        total_likes = 0
        total_comments = 0
        
        for item in real_content:
            total_unique_views += item.get('unique_views', 0)
            total_raw_views += item.get('total_views', 0)
            l_count = requests.get(f"{SUPABASE_URL}/rest/v1/likes?content_id=eq.{item['id']}&select=count", headers=HEADERS).json()[0]['count']
            c_count = requests.get(f"{SUPABASE_URL}/rest/v1/comments?content_id=eq.{item['id']}&select=count", headers=HEADERS).json()[0]['count']
            total_likes += l_count
            total_comments += c_count

        # MANIPULATION RESISTANCE CALCULATION
        suspicion_ratio = round(total_raw_views / total_unique_views, 2) if total_unique_views > 0 else 1.0
        status_label = "Clean 😊"
        status_class = "status-clean"
        if suspicion_ratio > 3.0: # Threshold for suspicion (average 3+ refreshes per human)
            status_label = "Suspicious 🚩"
            status_class = "status-suspicious"

        payout = calculate_dynamic_payout(total_unique_views, total_likes, total_comments)
        
        # Fetch real daily history (Simplified for demo)
        # In a real app: SELECT date(created_at), count(*) FROM views WHERE content_id IN (...) GROUP BY 1
        # For now, we'll just show the last few unique views with their real timestamps
        view_history_res = requests.get(f"{SUPABASE_URL}/rest/v1/views?select=created_at&limit=5", headers=HEADERS).json()
        real_history = []
        for v in view_history_res:
            real_history.append({"date": v['created_at'][:10], "views": "1 (Unique)"})

        return render_template('creator_overview.html', 
                               email=session.get('email'), 
                               total_views=total_unique_views,
                               raw_views=total_raw_views,
                               suspicion_ratio=suspicion_ratio,
                               status_label=status_label,
                               status_class=status_class,
                               payout=payout,
                               history=real_history)
    except Exception as e:
        print(f"Error in overview: {e}")
        return render_template('creator_overview.html', email=session.get('email'), total_views=0, payout=0, history=[])

@app.route('/transparency')
def transparency():
    if not login_required(role='admin'):
        return redirect(url_for('role_login', role='admin', error="Unauthorized access."))
        
    try:
        response = requests.get(f"{SUPABASE_URL}/rest/v1/users?role=eq.creator", headers=HEADERS)
        creators_list = response.json()
        
        display_creators = []
        for c in creators_list:
            content_res = requests.get(f"{SUPABASE_URL}/rest/v1/content?creator_id=eq.{c['id']}", headers=HEADERS).json()
            uv = sum(item.get('unique_views', 0) for item in content_res)
            rv = sum(item.get('total_views', 0) for item in content_res)
            
            ratio = round(rv / uv, 1) if uv > 0 else 1.0
            status = "Clean 😊"
            if ratio > 3.0: status = "Suspicious 🚩"
            
            display_creators.append({
                "name": c.get('email').split('@')[0],
                "views": f"{uv:,}",
                "ratio": f"{ratio}x",
                "payout": f"₹{calculate_dynamic_payout(uv, 0, 0)}", 
                "status": status
            })
            
        return render_template('transparency.html', creators=display_creators)
    except:
        return render_template('transparency.html', creators=[])

@app.route('/creator_transparency')
def creator_transparency():
    if not login_required(role='creator'):
        return redirect(url_for('role_login', role='creator', error="Unauthorized access."))
    
    # Fetch current creator's stats for live row
    api_url = f"{SUPABASE_URL}/rest/v1/content?creator_id=eq.{session['user_id']}"
    res = requests.get(api_url, headers=HEADERS).json()
    v = sum(item.get('unique_views', 0) for item in res)
    
    creators = [
        {"name": "Alice Johnson", "email": "alice@test.com", "unique_views": "10,200", "payout": "6,500", "status": "Paid"},
        {"name": "Eve Wilson", "email": "eve@test.com", "unique_views": "8,950", "payout": "5,400", "status": "Paid"},
        {"name": "You / Current Creator", "email": session.get('email'), "unique_views": f"{v:,}", "payout": "Live", "status": "Pending"},
    ]
    return render_template('creator_transparency.html', creators=creators, current_email=session.get('email'))

@app.route('/creator/add_content', methods=['GET', 'POST'])
def add_content():
    if not login_required(role='creator'):
        return redirect(url_for('role_login', role='creator', error="Unauthorized access."))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        try:
            data = {"creator_id": session['user_id'], "title": title, "description": description, "unique_views": 0}
            requests.post(f"{SUPABASE_URL}/rest/v1/content", headers=HEADERS, json=data)
            return redirect(url_for('content_library'))
        except Exception as e:
            return f"Database Error: {e}"
    return render_template('add_content.html')

@app.route('/creator/content_library')
def content_library():
    if not login_required(role='creator'):
        return redirect(url_for('role_login', role='creator', error="Unauthorized access."))
    try:
        api_url = f"{SUPABASE_URL}/rest/v1/content?creator_id=eq.{session['user_id']}"
        response = requests.get(api_url, headers=HEADERS)
        library = response.json()
        for item in library:
            item['color'] = "#A4D4F4"
            item['date'] = item.get('created_at', 'Today')[:10]
        return render_template('content_library.html', library=library)
    except:
        return render_template('content_library.html', library=[])

@app.route('/creator/content/<content_id>')
def content_detail(content_id):
    if not login_required(role='creator'):
        return redirect(url_for('role_login', role='creator', error="Unauthorized access."))
    try:
        api_url = f"{SUPABASE_URL}/rest/v1/content?id=eq.{content_id}"
        response = requests.get(api_url, headers=HEADERS)
        data = response.json()[0]
        ratio = 0
        if data['unique_views'] > 0:
            ratio = round(((data['likes'] + data['comments']) / data['unique_views']) * 100, 2)
        data['engagement_ratio'] = ratio
        return render_template('content_detail.html', content=data)
    except:
        return "Content not found", 404

@app.route('/admin/update_status', methods=['POST'])
def update_payout_status():
    if not login_required(role='admin'):
        return jsonify({"error": "Unauthorized"}), 403
    payout_id = request.json.get('payout_id')
    new_status = request.json.get('status')
    try:
        requests.patch(f"{SUPABASE_URL}/rest/v1/payouts?id=eq.{payout_id}", headers=HEADERS, json={"status": new_status})
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
else:
    # This is for Vercel
    application = app
