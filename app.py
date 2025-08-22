from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests, os, json

import warnings
from urllib3.exceptions import NotOpenSSLWarning
warnings.filterwarnings("ignore", category=NotOpenSSLWarning)

app = Flask(__name__)

#API_KEY = "sk_80bbd19f2243938ecba3502b576a2d88b0819c5ffb518b97"  Aurobinda Jena
API_KEY = "sk_a311ab548efa461af233a20bf1480de621413c006a32dca0" #AKr
#API_KEY = "sk_3e58265d00810754dc0ab01c4ae7d2349ba0f4a0c25e2eba"
BASE_URL = "https://api.elevenlabs.io/v1/convai/agents"
HEADERS = {"xi-api-key": API_KEY, "Content-Type": "application/json"}
ACTIVE_FILE = "active_agent.json"
KB_UPLOAD_URL = "https://api.elevenlabs.io/v1/convai/knowledge-base/file"
KB_UPLOAD_HEADERS = {"xi-api-key": API_KEY}  # do not set Content-Type here
KB_LIST_URL = "https://api.elevenlabs.io/v1/convai/knowledge-base"

@app.route("/kb_upload", methods=["POST"])
def kb_upload():
    kb_name = request.form.get("kb_name", "").strip()
    kb_file = request.files.get("kb_file")

    if not kb_name:
        return jsonify({"ok": False, "error": "Please enter a Knowledge Base name."}), 400
    if not kb_file or kb_file.filename == "":
        return jsonify({"ok": False, "error": "Please choose a .txt file to upload."}), 400

    files = {
       "file": (kb_file.filename+".txt", kb_file.stream, kb_file.mimetype)
       # 'file', (kb_file.filename, open(kb_file.filename, 'rb')),
    }
    data = {"name": kb_name+'.txt'}

    try:
        resp = requests.post(KB_UPLOAD_URL, headers=KB_UPLOAD_HEADERS, data=data, files=files, timeout=30)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Upload failed: {e}"}), 500

    # pass through ElevenLabs response without touching anything else
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}

    if resp.status_code == 200:
        # Expect: {"id": "...", "name": "..."}
        return jsonify({"ok": True, "kb": body}), 200
    else:
        return jsonify({"ok": False, "error": body}), resp.status_code


@app.route("/kb_list", methods=["GET"])
def kb_list():
    try:
        resp = requests.get(KB_LIST_URL, headers={"xi-api-key": API_KEY}, timeout=30)
    except Exception as e:
        return jsonify({"ok": False, "error": f"List failed: {e}"}), 500

    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}

    if resp.status_code == 200:
        # Expected shape is usually { "documents": [ ... ] } or a plain array depending on API
        return jsonify({"ok": True, "data": body}), 200
    else:
        return jsonify({"ok": False, "error": body}), resp.status_code
    

@app.route("/kb_delete/<doc_id>", methods=["DELETE"])
def kb_delete(doc_id):
    try:
        resp = requests.delete(f"{KB_LIST_URL}/{doc_id}", headers={"xi-api-key": API_KEY}, timeout=30)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Delete failed: {e}"}), 500

    # 204 No Content or 200 OK => success
    if resp.status_code in (200, 204):
        # Try to parse JSON if present; otherwise return empty data
        try:
            body = resp.json()
        except Exception:
            body = {}
        return jsonify({"ok": True, "data": body}), 200

    # Other codes => error, try to pass JSON or text
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text or f"HTTP {resp.status_code}"}
    return jsonify({"ok": False, "error": body}), resp.status_code

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

        # Prompt can come from textarea or .txt upload
        prompt_text = request.form.get("prompt", "")
        prompt_file = request.files.get("prompt_file")
        if prompt_file and prompt_file.filename.endswith(".txt"):
            prompt_text = prompt_file.read().decode("utf-8")

        # KB selection from dropdown
        kb_id = request.form.get("kb_id", "").strip()
        kb_name = ""
        if kb_id:
            # match id -> name from current KB catalog
            kbs = get_knowledge_bases()
            kb_name = next((kb["name"] for kb in kbs if kb["id"] == kb_id), "")

        knowledge_base = []
        if kb_id or kb_name:
            # EXACT structure: no "type", id allowed to be ""
            knowledge_base = [{"name": kb_name, "id": kb_id, "type": "file"}]

        payload = {
            "conversation_config": {
                "agent": {
                    "first_message": first_message,
                    "language": "en",
                    "prompt": {
                        "knowledge_base": knowledge_base,
                        "prompt": prompt_text
                    }
                },
                "asr": {
                    "quality": "high",
                    "provider": "elevenlabs",
                    "user_input_audio_format": "pcm_16000"
                },
                "turn": {
                    "silence_end_call_timeout": 20,
                },
                "tts": {
                    "voice_id": voice_id
                }
            },
            "name": name
        }

        print("📤 CREATE payload:\n", json.dumps(payload, indent=2))
        res = requests.post(f"{BASE_URL}/create", headers=HEADERS, json=payload)
        if res.status_code == 200:
            data = res.json()
            save_active_agent({"agent_id": data["agent_id"], "name": name})
            return redirect("/")
        return render_template("create.html", error=res.json(), knowledge_bases=get_knowledge_bases())

    # GET -> render with KB dropdown
    return render_template("create.html", knowledge_bases=get_knowledge_bases())


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

        prompt_text = request.form.get("prompt", "")
        prompt_file = request.files.get("prompt_file")
        if prompt_file and prompt_file.filename.endswith(".txt"):
            prompt_text = prompt_file.read().decode("utf-8")

        kb_id = request.form.get("kb_id", "").strip()
        kb_name = ""
        if kb_id:
            kbs = get_knowledge_bases()
            kb_name = next((kb["name"] for kb in kbs if kb["id"] == kb_id), "")

        knowledge_base = []
        if kb_id or kb_name:
            knowledge_base = [{"name": kb_name, "id": kb_id, "type": "file"}]

        payload = {
            "conversation_config": {
                "agent": {
                    "first_message": first_message,
                    "language": "en",
                    "prompt": {
                        "knowledge_base": knowledge_base,
                        "prompt": prompt_text
                    }
                },
                "asr": {
                    "quality": "high",
                    "provider": "elevenlabs",
                    "user_input_audio_format": "pcm_16000"
                },
                "tts": {
                    "voice_id": voice_id
                }
            },
            "name": name
        }

        print("📤 UPDATE payload:\n", json.dumps(payload, indent=2))
        res = requests.patch(f"{BASE_URL}/{agent_id}", headers=HEADERS, json=payload)
        if res.status_code == 200:
            save_active_agent({"agent_id": agent_id, "name": name})
            return redirect("/")
        # re-render with dropdown populated on error
        return render_template("update_form.html",
                               agent_id=agent_id,
                               agent={"name": name, "conversation_config": {"agent": {"prompt": {"prompt": prompt_text}}}},
                               error=res.json(),
                               knowledge_bases=get_knowledge_bases(),
                               selected_kb_id=kb_id)

    # GET → prefill form + KB dropdown + currently linked KB (if any)
    agent_detail = requests.get(f"{BASE_URL}/{agent_id}", headers=HEADERS).json()
    selected_kb_id = ""
    try:
        kb_list = agent_detail["conversation_config"]["agent"]["prompt"].get("knowledge_base", [])
        if kb_list and isinstance(kb_list, list):
            selected_kb_id = kb_list[0].get("id", "")
    except Exception:
        pass

    return render_template("update_form.html",
                           agent=agent_detail,
                           agent_id=agent_id,
                           knowledge_bases=get_knowledge_bases(),
                           selected_kb_id=selected_kb_id)


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

def get_knowledge_bases():
    """Return a normalized list of KB docs: [{'id': '...', 'name': '...'}, ...]."""
    try:
        resp = requests.get(
            "https://api.elevenlabs.io/v1/convai/knowledge-base",
            headers={"xi-api-key": API_KEY},
            timeout=30,
        )
        data = resp.json()
        # API may return a list or {"documents": [...]}
        docs = data.get("documents") if isinstance(data, dict) else data
        docs = docs if isinstance(docs, list) else []
        out = []
        for d in docs:
            out.append({
                "id": d.get("id") or d.get("document_id") or "",
                "name": d.get("name") or "Unnamed",
            })
        return out
    except Exception as e:
        print("KB fetch failed:", e)
        return []



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
