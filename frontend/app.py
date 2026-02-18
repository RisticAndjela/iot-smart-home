from flask import Flask, render_template, jsonify  # Dodat jsonify
from influxdb_client import InfluxDBClient
import os

app = Flask(__name__)

# --- PODEŠAVANJA ---
influx_url = "http://localhost:8086"
influx_token = "iot-super-token"     
influx_org = "FTN"                   
influx_bucket = "iot-sensor-report"  

client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)

def get_latest_sensor_data():
    query_api = client.query_api()
    query = f'from(bucket: "{influx_bucket}") |> range(start: -1h) |> last()'
    
    try:
        tables = query_api.query(query, org=influx_org)
        results = {}
        for table in tables:
            for record in table.records:
                device = record.values.get("device")
                results[device] = record.get_value()
        return results
    except Exception as e:
        print(f"Greška pri čitanju iz InfluxDB: {e}")
        return {}

@app.route('/')
def index():
    current_data = get_latest_sensor_data()
    return render_template('index.html', data=current_data)

# --- NOVA RUTA ZA AJAX OSVEŽAVANJE ---
@app.route('/api/data')
def get_data():
    current_data = get_latest_sensor_data()
    return jsonify(current_data)

if __name__ == '__main__':
    print("--- Flask aplikacija se pokreće na http://localhost:5000 ---")
    app.run(debug=True, port=5000)