# python_ChatGPT_TelegramBot
Telegram messenger bot which uses ChatGPT.

## ToDo:
 * Better error handling -> work in progres..
  * translations (de, en) -> work in progres..

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
  * Create a "menu" for your bot with the following commands (BotFather -> Edit Bot -> Edit Commands)..
    - e.G:

            model - Change used model
            topic - create, change or delete a topic
            chat - Chat with ChatGPT
            cancel - Cancel current operation

  * Use the "Menu" left of the input field..
    - "Chat" start the chat. Each message is send to the ChatGPT API. A response may 
take a few seconds.
      
 A "Topic" can be used to have a context for ChatGPT. It uses the last mmessages, so e.g. you can enhance an answer or give some more context or get better results.
