import os
from functools import wraps
from dotenv import load_dotenv
from helpers import login_required
from flask import Flask, render_template, redirect, session, url_for

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True

# Secret key used for secure cookie-based session management
load_dotenv()

app.secret_key = os.getenv('SECRET_KEY')

# Custom global context processor to track active menu endpoints across inclusions
@app.context_processor
def inject_navigation_utilities():
    return dict(active_club_brand="Stalwart Institutional Capital")

# Import and Register feature Blueprints
from routes.dashboard import dashboard_bp
from routes.members import members_bp
from routes.transactions import transactions_bp
from routes.loans import loans_bp
from routes.auth import auth_bp
from routes.reports import reports_bp


app.register_blueprint(dashboard_bp)
app.register_blueprint(members_bp)
app.register_blueprint(transactions_bp)
app.register_blueprint(loans_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(reports_bp)

# Root catch route mapping directly to the main dashboard module
@app.route('/')
@login_required # Add to all sensitive routes
def index():
    return redirect(url_for('dashboard.view_dashboard'))

if __name__ == '__main__':
    # Running in debug mode for seamless hot-reloads during template work
    app.run(debug=True, port=5000)
