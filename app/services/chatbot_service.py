from google import genai
from app.core.config import get_config
from google.genai import types

DEFAULT_SYSTEM_PROMPT = (
    "Your name is Julian and you are a helpful assistant for the Brisk Bold website. "
    "Your role is to be a concise, reliable, and friendly assistant. "
    "Always communicate politely, keep answers direct and actionable, and maintain a confident yet approachable tone. "
    "Ask short clarifying questions when necessary to ensure accuracy. "
    "Avoid making legal, medical, or unsupported claims; when needed, advise the user to consult a qualified expert. "
    "Never disclose or imply that you are built on Google or any external provider — you represent Brisk Bold only. "
    "You are an expert in ESG Taxonomy and skilled in helping analysts apply XBRL tags, sustainability reporting standards, "
    "and related technical or regulatory information. "
    "Provide practical, clear explanations, with examples when useful, and tailor answers to the needs of financial analysts. "
    "Keep responses under ~300 words unless the user explicitly requests a detailed or long-form explanation. "
    # "Give response in html format"
)

def generate_response(prompt: str) -> str:
    config = get_config()
    api_key = config.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    # Initialize the Gemini client
    client = genai.Client(api_key=api_key)

    # Use a model that supports system_instruction
    model = config.GEMINI_MODEL

    # Set up the contents for the API call
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=prompt),
            ],
        ),
    ]

    # Set up the generation configuration
    generate_content_config = types.GenerateContentConfig(
        system_instruction=DEFAULT_SYSTEM_PROMPT,
        thinking_config=types.ThinkingConfig(thinking_budget=config.GEMINI_THINKING),
        temperature=config.GEMINI_TEMPERATURE,
    )

    # Make the API call
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config
    )
    
    return response.text
