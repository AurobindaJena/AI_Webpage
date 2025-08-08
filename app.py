from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

ELEVEN_API_KEY = "sk_80bbd19f2243938ecba3502b576a2d88b0819c5ffb518b97"
AGENT_CREATE_URL = "https://api.elevenlabs.io/v1/convai/agents/create"

latest_agent = {}

@app.route('/')
def index():
    return render_template('create_agent.html')

@app.route('/create_agent', methods=['POST'])
def create_agent():
    name = request.form.get('name')
    first_message = request.form.get('first_message')
    prompt_text = request.form.get('prompt')
    voice_id = request.form.get('voice_id')

    headers = {
        "xi-api-key": ELEVEN_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "name": name,
        "conversation_config": {
            "agent": {
                "first_message": first_message,
                "language": "en",
                "prompt": {
                    "prompt": prompt_text
                }
            },
            "asr": {
                "quality": "high",
                "provider": "elevenlabs",
                "user_input_audio_format": "pcm_16000",
                "keywords": []
            },
            "turn": {},
            "tts": {
                "voice_id": voice_id
            },
            "conversation": {},
            "language_presets": {}
        }
    }

    response = requests.post(AGENT_CREATE_URL, headers=headers, json=payload)
    result = response.json()

    if response.status_code == 200 and "agent_id" in result:
        global latest_agent
        latest_agent = {
            "agent_id": result["agent_id"],
            "name": name
        }
        return render_template('create_agent.html', success=True, agent=latest_agent)
    else:
        return render_template('create_agent.html', error=result)

@app.route('/get_agent', methods=['GET'])
def get_agent():
    return jsonify(latest_agent) if latest_agent else jsonify({"error": "No agent created yet"}), 200

if __name__ == '__main__':
    #app.run(debug=True, host = '0.0.0.0' ,port=8080)
    port = int(os.environ.get("PORT",5000))
    app.run(debug=True, host="0.0.0.0", port=port)
