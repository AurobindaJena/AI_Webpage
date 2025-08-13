from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests, os, json

import warnings
from urllib3.exceptions import NotOpenSSLWarning
warnings.filterwarnings("ignore", category=NotOpenSSLWarning)

app = Flask(__name__)

API_KEY = "sk_80bbd19f2243938ecba3502b576a2d88b0819c5ffb518b97"
BASE_URL = "https://api.elevenlabs.io/v1/convai/agents"
HEADERS = {"xi-api-key": API_KEY, "Content-Type": "application/json"}
ACTIVE_FILE = "active_agent.json"

def load_active_agent():
    if os.path.exists(ACTIVE_FILE):
        with open(ACTIVE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_active_agent(agent):
    with open(ACTIVE_FILE, "w") as f:
        json.dump(agent, f)

# ✅ Home page: show current + agent list
@app.route("/")
def index():
    active = load_active_agent()
    res = requests.get(BASE_URL, headers=HEADERS)
    agents = res.json().get("agents", [])
    return render_template("index.html", active_agent=active, agents=agents)

# ✅ Create agent
@app.route("/create", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        name = request.form["name"]
        voice_id = request.form["voice_id"]
        first_message = request.form["first_message"]
        prompt = request.form.get("prompt", "")
        prompt_file = request.files.get("prompt_file")

        if prompt_file and prompt_file.filename.endswith(".txt"):
            prompt = prompt_file.read().decode("utf-8")

        payload = {
            "name": name,
            "conversation_config": {
                "agent": {
                    "first_message": first_message,
                    "language": "en",
                    "prompt": { "prompt": prompt }
                },
                "asr": {
                    "quality": "high",
                    "provider": "elevenlabs",
                    "user_input_audio_format": "pcm_16000",
                    "keywords": []
                },
                "turn": {},
                "tts": { "voice_id": voice_id },
                "conversation": {},
                "language_presets": {}
            }
        }

        res = requests.post(f"{BASE_URL}/create", headers=HEADERS, json=payload)
        if res.status_code == 200:
            data = res.json()
            save_active_agent({ "agent_id": data["agent_id"], "name": name })
            return redirect("/")
        return render_template("create.html", error=res.json())

    return render_template("create.html")

# ✅ Update - select
@app.route("/update", methods=["GET", "POST"])
def update_select():
    res = requests.get(BASE_URL, headers=HEADERS)
    agents = res.json().get("agents", [])
    if request.method == "POST":
        agent_id = request.form["agent_id"]
        return redirect(url_for("update_form", agent_id=agent_id))
    return render_template("update_select.html", agents=agents)

# ✅ Update - form
@app.route("/update/<agent_id>", methods=["GET", "POST"])
def update_form(agent_id):
    if request.method == "POST":
        name = request.form["name"]
        voice_id = request.form["voice_id"]
        first_message = request.form["first_message"]
        prompt = request.form.get("prompt", "")
        prompt_file = request.files.get("prompt_file")
        if prompt_file and prompt_file.filename.endswith(".txt"):
            prompt = prompt_file.read().decode("utf-8")

        payload = {
            "name": name,
            "conversation_config": {
                "agent": {
                    "first_message": first_message,
                    "language": "en",
                    "prompt": {"prompt": prompt}
                },
                "tts": {"voice_id": voice_id}
            }
        }

        res = requests.patch(f"{BASE_URL}/{agent_id}", headers=HEADERS, json=payload)
        if res.status_code == 200:
            save_active_agent({"agent_id": agent_id, "name": name})
            return redirect("/")
        return render_template("update_form.html", agent_id=agent_id, error=res.json())

    agent_detail = requests.get(f"{BASE_URL}/{agent_id}", headers=HEADERS).json()
    return render_template("update_form.html", agent=agent_detail, agent_id=agent_id)

# ✅ Delete agent
@app.route("/delete", methods=["GET", "POST"])
def delete():
    res = requests.get(BASE_URL, headers=HEADERS)
    agents = res.json().get("agents", [])
    if request.method == "POST":
        agent_id = request.form["agent_id"]
        requests.delete(f"{BASE_URL}/{agent_id}", headers=HEADERS)
        if load_active_agent().get("agent_id") == agent_id:
            save_active_agent({})
        return redirect("/")
    return render_template("delete.html", agents=agents)

# ✅ Select agent (set active)
@app.route("/select_agent", methods=["POST"])
def select_agent():
    agent_id = request.form["agent_id"]
    res = requests.get(f"{BASE_URL}/{agent_id}", headers=HEADERS)
    if res.status_code == 200:
        agent_data = res.json()
        agent_info = {
            "agent_id": agent_id,
            "name": agent_data.get("name", "Unnamed Agent"),
            "conversation_config": agent_data.get("conversation_config", {})
        }
        save_active_agent(agent_info)
        return redirect("/")
    return "Agent not found", 404

# ✅ Return current agent for Android
@app.route("/get_agent")
def get_agent():
    agent = load_active_agent()
    if agent:
        return jsonify(agent)
    return jsonify({ "error": "No agent selected or created." }), 404

# ✅ Return API key
@app.route('/get_apikey', methods=['GET'])
def get_apikey():
    if API_KEY:
        return jsonify({ "api_key": API_KEY })
    return jsonify({ "error": "No API Key found" }), 404

# ✅ Run app
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host="0.0.0.0", port=port)
