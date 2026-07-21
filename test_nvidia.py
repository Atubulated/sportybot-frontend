from openai import OpenAI

# 1. Initialize the client with NVIDIA's base URL and your API key
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key="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" # Replace with your real key
)

# 2. Define the professional sports analysis prompt
system_prompt = "You are a premium, institutional-grade sports data analyst. Your responses must be concise, professional, and strictly based on the provided data."

user_prompt = """
Analyze the following match data and provide a structured prediction.

Raw Data: 
- Match: Arsenal vs Chelsea
- Arsenal Form: Won last 3 home games, scoring an average of 2.1 goals per game.
- Chelsea Form: 2 key starting defenders are injured. Won 1 of last 4 away games.
- Current Market Odds: Arsenal 1.85, Draw 3.60, Chelsea 4.20

Output format:
1. Predicted Outcome:
2. Confidence Level (0-100%):
3. Key Reasoning (2 sentences max):
4. Value Assessment (Yes/No):
"""

# 3. Make the API call using the 70B model
completion = client.chat.completions.create(
    model="meta/llama-3.3-70b-instruct",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    temperature=0.2,
    top_p=0.7,
    max_tokens=500,
    stream=False
)

# 4. Print the clean result
print("--- AI ANALYSIS ---")
print(completion.choices[0].message.content)
print("-------------------")