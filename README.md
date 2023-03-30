# python_ChatGPT_TelegramBot
Telegram messenger bot which uses ChatGPT.

## Preconditions:
  * OpenAI access token [API keys](https://platform.openai.com/account/api-keys)
  * Telegram bot token (@BotFather) in the Telegram application.
  * For each telegram user which shoud be allowed to use the bot the telegram ID given from @userinfobot.
  * PC which can run python3 programms.

## Install:
  * Clone this repository.
  * Install python packages with "pip3 install openai python-telegram-bot"
  * Edit the "config_example.json" and save it as "config.json".
    - "opeanai_key" -> the opeanai secret key
    - "telegram_token" -> the telegram bot token
    - "users" -> list of allowed users as "ID#NAME"

## Useage:
  * Use the "Menu" left of the input field..
    - "Chat" start the chat. Each message is send to the ChatGPT API. A response may 
take a few seconds.
    - With "Themen" you can ..
      - start a new topic (neues Thema)
      - resume a existing topic (vorhandenes Thema)
      - continue without a topic (ohne Thema)
      - show the current active topic (zeige aktuelles Thema)
      - delete a topic (lösche Thema)
      - (abbrechen) -> cancel the current action
      
 A "Topic" can be used to have a context for ChatGPT. It uses the last mmessages, so e.g. you can enhance an answer or give some more context or get better results.
 
