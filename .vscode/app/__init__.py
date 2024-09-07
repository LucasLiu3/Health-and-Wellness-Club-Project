
from flask import Flask

app = Flask(__name__,template_folder='../templates',static_folder='../static')



from app import home
from app import authentication
from app import therapist_view
from app import member_view
from app import manager_view

