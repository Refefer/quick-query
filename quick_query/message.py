RE2_PROMPT = "{message}\nRead the question again:\n{message}"
class MessageProcessor:
    def __init__(self, re2=False):
        self.re2 = re2

    def process_user_prompt(self, prompt):
        if self.re2:
            prompt = RE2_PROMPT.format(message=prompt)

        return {"role": "user", "content": prompt}
