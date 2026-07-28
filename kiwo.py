from ollama import chat 
from huggingface_hub import InferenceClient
import json
import os
from openai import OpenAI
from datetime import datetime, timedelta
import random
import requests


PROVIDER = "hf"

OLLAMA_MODEL = "qwen3:4b"
HF_MODEL     = "Qwen/Qwen2.5-7B-Instruct:together"  
HF_TOKEN     = os.environ.get("HF_TOKEN")


if PROVIDER.lower() == "ollama":
    client = OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama"
    )
    MODEL = OLLAMA_MODEL

elif PROVIDER.lower() == "hf":
    client = OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=HF_TOKEN
    )
    MODEL = HF_MODEL






# init the state
# the state is created by the agent, but stored outside of the LLM
# THe state is injeced into the system prompt for higher pryority
# one could also store states on harddrive to reused user-preferences in a new session (overkill for the KiWo bot)
state = {
    "date": None,
    "weather": None,
    "time": None,
    "user_preferences": None
}


def mychat(message_log, state):
    # inject state into system prompt
    enriched_log = message_log.copy()
    enriched_log.insert(1, {
        "role": "system",
        "content": f"CURRENT STATE:\n{json.dumps(state, default=str)}"
    })

    completion = client.chat.completions.create(
        model=MODEL,
        messages=enriched_log,
        max_tokens=512,
        temperature=0,
        top_p=1,
        response_format={"type": "json_object"}
    )

    answer = completion.choices[0].message.content

    message_log.append({
        "role": "assistant",
        "content": answer
    })

    return message_log, answer


def user_msg(msg: str):
    return {"role": "user", "content": msg}

def assistant_msg(msg: str):
    return {"role": "assistant", "content": msg}

def system_msg(msg: str):
    return {"role": "system", "content": msg}





def get_weather_kiel(target_datetime: datetime):
    
    
    # type conversion to datetime object
    if isinstance(target_datetime, datetime):
        pass  # already a valid datetime (possibly only happens, when a not-LLM calls this function)
    elif isinstance(target_datetime, str):
        try:
            target_datetime = datetime.fromisoformat(target_datetime)
        except ValueError:
            # fall back for plain date strings like "2026-06-26"
            target_datetime = datetime.strptime(target_datetime, "%Y-%m-%d")
    else:
        raise TypeError(
            f"target_datetime must be a datetime or string, got {type(target_datetime)}"
        )
    
    
    # The current datetime is used to either look into the real forecast or to look into the forecast archive
    now = datetime.now()
    date_str = target_datetime.strftime("%Y-%m-%d")
    KIEL_LAT = 54.3233
    KIEL_LON = 10.1228

    if target_datetime > now:
        # Future -> forecast API
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": KIEL_LAT,
            "longitude": KIEL_LON,
            "start_date": date_str,
            "end_date": date_str,
            "hourly": "temperature_2m,precipitation,weathercode,windspeed_10m",
            "timezone": "Europe/Berlin",
        }
    else:
        # Past (or now) -> historical/archive API
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": KIEL_LAT,
            "longitude": KIEL_LON,
            "start_date": date_str,
            "end_date": date_str,
            "hourly": "temperature_2m,precipitation,weathercode,windspeed_10m",
            "timezone": "Europe/Berlin",
        }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()




def get_date():
    """Returns the datetime. If the real datetime is not during the KiWO 2026, a random datetime from the KiWo is returned.
    This is obviously only for debugging reasons. 

    Returns:
        datetime: _
    """
    now = datetime.now()
    
    # start and end of the KiWO (hardcoded, but I don't want the agent to access this values)    
    window_start = datetime(2026, 6, 20)
    window_end = datetime(2026, 6, 28)
    
    # If KiWO is now, return the real datetime
    if window_start <= now <= window_end:
        return now
    
    # Return a random datetime of the KiWo
    delta = window_end - window_start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return window_start + timedelta(seconds=random_seconds)


def get_activities(description):
    """returns the whole KiWO programm. The description of the agent is not used right now.
    The functions only expects the description to force the agent to think of a usefull description, simulating a RAG pipeline (only for my educational purpose, completly useless for production).
    The function could be bumped up to a RAG pipeline for larger documents.
    Args:
        description (str): Type of event, the agent has in mind.

    Returns:
        dict: complete KiWo programm
    """
    # Can be uncommented for debugging
    #print(f"Description formulated by hte agent: {description}")
    with open("programm.json") as f:
        pr = json.load(f)
    return pr


def answer(answer_text):
    """The query of the LLM to the user is also handled as a tool in json format. This makes the system prompt a bit less confusing.

    Args:
        answer_text (str): The mssage, the LLM wants to send to the user.

    Returns:
        str: Whateer the user wrote.
    """
    print(answer_text)
    user_input = input("\nUser: ")
    if user_input.lower() in ["exit", "quit"]:
        quit()
    return user_input


def make_obervation(obs):
    """String output of an action get transformed into json format to feed back to the agent.

    Args:
        obs (str): _

    Returns:
        json: _
    """
    j_obs = json.dumps({"type": "observation",
                "data": obs,
    }, default=str)
    return j_obs



# dct, containing all functions, the gant can call.
function_dict = {
    "get_date": get_date,
    "get_weather_kiel": get_weather_kiel,
    "get_activities": get_activities,
    "answer": answer,
}

system_prompt = """
You are a chat assistant that helps to find activities for the Kieler Woche (KiWo), a sailing and festival event in Kiel, germany.
You operate as a tool-usig agent in a loop consisting of THOUGHT, ACTION, STOP, OBSERVATION. 
You output only actions and you retrieve observations.


possible actions:
- get_date: arguments: none. Returns the current datetime.
- get_weather_kiel: arguments: {"target_datetime": "<ISO date string, e.g. 2026-06-26>"}. Returns the weather for that date.
- get_activities: arguments: {"description": "<string describing the type of activity you're looking for>"}. Returns matching activities with time and place.
- answer: arguments: {"answer_text": "<the message to show the user>"}. Sends a message to the user and waits for their reply.

All information you gather are stored in an external memory STATE. 

The STATE contains all information you alsready gathered.
You can update the STATE each time you produce an output.
You update the state based on information you gained from tool use or from user input.

You must use the state to decide on tool calls or answers.



output format:
You output ONLY in valid json format. 
Do NOT include other explanations.
Do NOT include markdown.

examples:
Examples of your output:

{ "type":"action",
  "thought": "I need to know today's date before checking weather and activities.",
  "action": "get_date",
  "args": {},
  "state":{"date": null, 
          "weather":null, 
          "time":null, 
          "user_preferences":null}
}

{ "type":"action",
  "thought": "The 420 sailing race could be an interesting activity for the user.",
  "action": "answer",
  "args": {"answer_text": "You could attend the 420 sailing race at 18:00 today. Does this interest you?"},
  "state":{"date": "26 June 2026", 
          "weather":"sunny", 
          "time":14:56, 
          "user_preferences":"Sailing events. The user was not interested in the Laser sailing race at 17.00."}
}


Examples of observations you retrieve:
{
  "type": "observation",
  "data": "What can I do at the kiwo today?",
  "state":{"date": null, 
          "weather":null, 
          "time":null, 
          "user_preferences":null}
}

{
  "type": "observation",
  "data": "I am not interested in Laser sailing race.",
  "state":{"date": "26 June 2026", 
          "weather":"sunny", 
          "time":"14:56", 
          "user_preferences":"Sailing events."}
}



"""






# init log and write the system prompt
log = []
log.append(system_msg(system_prompt))




first_user = answer("Hi, how can I help you today?")
json_obs = make_obervation(first_user)
log.append(user_msg(json_obs))
    

# main ReACT loop
while True:
    log, ans = mychat(message_log=log, state=state)
    try:
        data = json.loads(ans)
    except json.JSONDecodeError:
        print("Invalid JSON from model")
        break
    
    tool = data["action"]
    args = data.get("args", {})
    state = data['state']
    #print(tool)
    if tool not in function_dict:
        observation = f"Unknown tool: {tool}"
    else:
        observation = function_dict[tool](**args)
    json_obs = make_obervation(observation)
    log.append(user_msg(json_obs))
    
