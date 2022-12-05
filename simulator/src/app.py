from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route('/stats/avg/<string:stat_name>/<int:duration>')
def average(stat_name, duration):
    return jsonify(
        {
            "stat_name": stat_name,

            "duration": duration
        }
    )


@app.route('/stats/current/<string:stat_name>')
def current(stat_name):
    return jsonify(
        {
            "stat_name": stat_name
        }
    )


app.run(port=5000)
