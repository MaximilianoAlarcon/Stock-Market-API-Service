from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests, random, string, pandas as pd, os

app = Flask(__name__)
#API throttling, prevents spam and hacking
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

#Make a request to Alpha Vantage API
def send_request(URL):
	r = requests.get(url = URL)
	return r.json()

#Generate an api key after sign up
def generate_key(length):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

#Check if the credentials exists in the database
def validate_permission(APIKEY,NAME,EMAIL):
	db = pd.read_csv(os.environ.get('DB_FILE', None))
	mask = (db["name"] == NAME) & (db["API_KEY"] == APIKEY) & (db["email"] == EMAIL)
	return mask.sum() == 1

#Check if a string containes substrings in list
def string_contains(str,lista):
	return any(x in str for x in lista)

#Check if a user already exists
def user_exists(db,data):
	mask = (db["name"] == data["name"]) & (db["last_name"] == data["last_name"]) & (db["email"] == data["email"])
	return mask.sum() > 0

#The header must contains only strings
def validate_header(APIKEY,NAME,EMAIL):
	return isinstance(APIKEY,str) and isinstance(NAME,str) and isinstance(EMAIL,str)

#This function validates the credentials and send the request to Alpha Vantage API
def get_data_validation(data,APIKEY,NAME,EMAIL):
	required_parameters = ["function","symbol","interval"]
	if all(x in data for x in required_parameters):
		if validate_permission(APIKEY,NAME,EMAIL):
			url = "https://www.alphavantage.co/query?"
			for key, value in data.items():
				url += str(key) + "=" + str(value) + "&"
			url += "apikey="+os.environ.get('API_KEY', None)
			result = send_request(url)
			return result
		else:
			return {"error_message":"You are not authorized to use this API"}
	else:
		return {"error_message":"Please, define the required parameters 'function','symbol','interval','name','email' and 'APIKEY' with their correct values. https://www.alphavantage.co/documentation/"}

#This function inserts new users in the database and return their APIKEYS
def sign_data_validation(data):
	required_parameters = ["name","last_name","email"]
	sql_inyection_sentences = ["'",'"',"*","delete ","update ","create ","drop ","select ","=","!","¡","truncate ","from ","database ",";"]
	if all(x in data for x in required_parameters):
		user_data = [data["name"],data["last_name"],data["email"]]
		if any(string_contains(string.lower(),sql_inyection_sentences) for string in user_data):
			return {"error_message":"Please, write the parameters without special characters and sentences"}
		else:
			db = pd.read_csv(os.environ.get('DB_FILE', None))
			if user_exists(db,data):
				return {"error_message":"This account already exists."}
			else:
				API_KEY = generate_key(40)
				mask_apikey = db["API_KEY"] == API_KEY
				while mask_apikey.sum() > 0:
					API_KEY = generate_key(40)
					mask_apikey = db["API_KEY"] == API_KEY
				db = db.append({'name': data["name"],'last_name': data["last_name"],'email': data["email"],'API_KEY': API_KEY}, ignore_index=True)
				db.to_csv("database.csv",index=False)	
				return {"message":"Thank you for your time. These are your credentials, make sure to add your NAME ("+data["name"]+"), EMAIL ("+data["email"]+") and APIKEY ("+API_KEY+") to the header for the data request. API KEY = "+API_KEY}
	else:
		return {"error_message":"Please, define the required parameters 'name','last_name' and 'email'."}


#Endpoint to register users
@app.route("/sign_up", methods = ['POST'])
@limiter.limit("1/second", override_defaults=False)
@limiter.limit("5/minute", override_defaults=False)
def sign_up():
	if request.method == 'POST':
		data = request.get_json(force=True)
		data = sign_data_validation(data)
		return jsonify(data)
	else:
		return jsonify({"error_message":"The method request is not correct"})

#Endpoint to request data from Alpha Vantage API
@app.route("/get_data", methods = ['POST'])
@limiter.limit("1/second", override_defaults=False)
@limiter.limit("5/minute", override_defaults=False)
def get_data():
	if request.method == 'POST':
		APIKEY = request.headers.get('APIKEY')
		NAME = request.headers.get('NAME')
		EMAIL = request.headers.get('EMAIL')
		if validate_header(APIKEY,NAME,EMAIL):
			data = request.get_json(force=True)
			data = get_data_validation(data,APIKEY,NAME,EMAIL)
			return jsonify(data)
		else:
			return jsonify({"error_message":"Please sign up to be get your API KEY and use this endpoint"})
	else:
		return jsonify({"error_message":"The method request is not correct"})


@app.route('/')
def index():
  return "<h1>Stock Market API Service</h1>"

#The app is running in a public IP
#if __name__ == "__main__":
#	app.run(host='0.0.0.0', port=8050)