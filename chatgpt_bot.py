# -*- coding: utf-8 -*-

import os
import sys
import json
import openai
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters
)

# -------------------------------------------------------------------------------------

class User:
    def __init__(self, name:  str, id: int, path: str, max_entries):
        self.name = name
        self.id = id
        self.path = path
        self.max_entries = max_entries
        self.data = None

    def save(self) -> None:
         with open(self.path, 'w') as outfile:
                        json.dump(self.data, outfile)
    
    def hasActiveTopic(self) -> bool:
        return not self.data['current_topic'] == ""
    
    def topics(self):
        topics = []
        for topic in self.data['topics']:
            topics.append(topic['name'])
        return topics
    
    def historyOfTopic(self, topic: str):
        for my_topic in self.data['topics']:
            if my_topic['name'] == topic:
                return my_topic['history']
        return []
    
    def updateHistory(self, topic: str, history):
        for my_topic in self.data['topics']:
            if my_topic['name'] == topic:
                while len(history) > self.max_entries:
                    history.pop(0)
                my_topic['history'] = history

# -------------------------------------------------------------------------------------

class Config:
    def __init__(self):
        config = self._loadFile()
        self.openai_key = config['opeanai_key']
        self.telegram_token = config['telegram_token']
        self.max_history_entries = config['max_history_entries']
        self.users = []
        for user in config['users']:
            if user:
                values = user.split("#")
                path = './chats/topics_{}.json'.format(values[1])
                user = User(values[1], values[0], path, self.max_history_entries * 2)
                self.users.append(user)

                # setup some filesystem operations
                if not os.path.exists(path):
                    json_data = {"current_topic": "", "topics": []}
                    user.data = json_data
                    with open(path, 'w') as outfile:
                        json.dump(json_data, outfile)
                else:
                    userdata = open(path, encoding='utf-8-sig')
                    json_data = json.load(userdata)
                    user.data = json_data

    def _loadFile(self):
        # load the configuration ..
        try:
            configFile = open("config.json", encoding='utf-8-sig')
            config = json.load(configFile)
            configFile.close()
            return config
        except IOError:
            print("Could not read config file!")
            sys.exit()
        except json.JSONDecodeError:
            print("config.json: decode error!")
            sys.exit()

# -------------------------------------------------------------------------------------

class OpenaAI_API:
    def __init__(self, key: str) -> None:
        openai.api_key = key
        self.model = "gpt-3.5-turbo"
        self.query = [{"role": "user", "content": ""}]

    def setModel(self, new_model: str) -> None:
        models = openai.Model.list()
        if new_model in models['data']:
            self.model = new_model

    def setQueryText(self, text: str) -> None:
        self.query[0]['content'] = text

    def getResponse(self) -> str:
        completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=self.query)
        return completion.choices[0].message.content

# -------------------------------------------------------------------------------------

class ChatGPTBot:
    def __init__(self, config : Config, openaiAPI : OpenaAI_API) -> None:
        self.config = config
        self.openai_api = openaiAPI
        self.updater = Application.builder().token(self.config.telegram_token).build()

        # add event handlers..
        self.updater.add_handler(CommandHandler('h', self.help))
        self.updater.add_handler(CommandHandler('help', self.help))
        self.updater.add_handler(CommandHandler('hilfe', self.help))
        self.updater.add_handler(CommandHandler('start', self.start))

        # conversations
        self.SELECTION, self.TOPICSELECTION, self.TOPICSELECTION_DELETE, self.NEWTOPIC = range(4)
        topic_handler = ConversationHandler(
            entry_points = [CommandHandler("topic", self.topic)],
            states = {
                self.SELECTION: [
                    MessageHandler(filters.Regex("^neues Thema$"), self.newtopic),
                    MessageHandler(filters.Regex("^vorhandenes Thema$"), self.existingtopic),
                    MessageHandler(filters.Regex("^ohne Thema$"), self.cleartopic),
                    MessageHandler(filters.Regex("^zeige aktuelles Thema$"), self.currenttopic),
                    MessageHandler(filters.Regex("^lösche Thema$"), self.deletetopic),
                    MessageHandler(filters.Regex("^abbrechen$"), self.cancel)
                ],
                self.TOPICSELECTION: [
                    MessageHandler(filters.Regex(".*"), self.setselectedtopic)
                ],
                self.TOPICSELECTION_DELETE: [
                    MessageHandler(filters.Regex(".*"), self.deleteselectedtopic)
                ],
                self.NEWTOPIC: [
                    MessageHandler(filters.Regex(".*"), self.newtopicname)
                ]
            }, fallbacks=[CommandHandler("cancel", self.cancel)])
        self.updater.add_handler(topic_handler)

        self.CHAT = range(1)
        chat_handler = ConversationHandler(
            entry_points = [CommandHandler('chat', self.chat_query)],
            states = {
                self.CHAT: [
                    MessageHandler(filters.Regex(".*"), self.chat_query)
                ]
            }, fallbacks=[CommandHandler("cancel", self.cancel)])
        self.updater.add_handler(chat_handler)
        
    async def topic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if self._isUser(update):
            reply_keyboard = []
            reply_keyboard.append(["neues Thema"])
            reply_keyboard.append(["vorhandenes Thema"])
            reply_keyboard.append(["ohne Thema"])
            reply_keyboard.append(["zeige aktuelles Thema"])
            reply_keyboard.append(["lösche Thema"])
            reply_keyboard.append(["abbrechen"])
            await update.message.reply_text("Wie kann ich helfen?", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True))
        return self.SELECTION
        
    async def newtopic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("not implemented yet")
        await update.message.reply_text("Thema?\nMöglichst als ein Wort!")
        return self.NEWTOPIC
    
    async def newtopicname(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        user.data['current_topic'] = update.message.text
        if update.message.text in user.topics():
            await update.message.reply_text("Thema existiert schon und ist jetzt aktiv!")
        else:
            user.data['topics'].append({"name": update.message.text.strip(), "history": []})
            user.data
        user.save()
        await update.message.reply_text("OK")
        return ConversationHandler.END

    async def existingtopic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        reply_keyboard = []
        topics = user.topics()
        for topic in topics:
            reply_keyboard.append([topic])
        await update.message.reply_text("Deine Themen:", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True))
        return self.TOPICSELECTION

    async def setselectedtopic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        user.data['current_topic'] = update.message.text
        user.save()
        await update.message.reply_text("OK")
        return ConversationHandler.END

    async def cleartopic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        user.data['current_topic'] = ""
        user.save()
        await update.message.reply_text("OK")
        return ConversationHandler.END
    
    async def currenttopic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        if user.hasActiveTopic():
            await update.message.reply_text("aktuelles Thema:\n{}".format(user.data['current_topic']))    
        else:
            await update.message.reply_text("aktuelles Thema:\n keines")
        return ConversationHandler.END

    async def deletetopic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        reply_keyboard = []
        topics = user.topics()
        for topic in topics:
            reply_keyboard.append([topic])
        await update.message.reply_text("Deine Themen:", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True))
        return self.TOPICSELECTION_DELETE
    
    async def deleteselectedtopic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        if user.data['current_topic'] == update.message.text:
            user.data['current_topic'] = ""
        counter = 0
        for topic in user.data['topics']:
            if update.message.text == topic['name']:
                del user.data['topics'][counter]
            else:
                counter += 1
        user.save()
        await update.message.reply_text("OK")
        return ConversationHandler.END

    async def topicname(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("not implemented yet")
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("OK")
        return ConversationHandler.END

    def run(self) -> None:
        print("listening..")
        self.updater.run_polling()

    def _isUser(self, update: Update) -> bool:
        userId = str(update.message.from_user.id)
        for user in self.config.users:
            if user.id == userId:
                return True
        return False
    
    def userById(self, update: Update) -> User:
        for user in self.config.users:
            userId = str(update.message.from_user.id)
            if user.id == userId:
                return user
    
    async def start(self, update, context):
        if self._isUser(update):
            await update.message.reply_text("Wilkommen beim ChatGPT Telegram Bot!")
        else:
            await update.message.reply_text("You are not in the valid users list!")

    async def help(self, update, context):
        if self._isUser(update):
            await update.message.reply_text("Wilkommen beim ChatGPT Telegram Bot!")
        else:
            await update.message.reply_text("You are not in the valid users list!")

    async def chat_query(self, update, context):
        if self._isUser(update):
            # filter commands
            if update.message.text == "/cancel":
                await update.message.reply_text("OK")
                return ConversationHandler.END
            elif update.message.text[0] == "/":
                return self.CHAT
            # chat with or without history..
            else:
                user = self.userById(update)
                response = ""
                if user.hasActiveTopic(): # chat with active topic
                    currentTopic = user.data['current_topic']
                    currentHistory = user.historyOfTopic(currentTopic)
                    currentHistory.append(update.message.text)
                    new_query_with_history = "\n".join(currentHistory)
                    openai_api.setQueryText(new_query_with_history)
                    response = openai_api.getResponse()
                    currentHistory.append(response)
                    user.updateHistory(currentTopic, currentHistory)
                    user.save()
                else: # chat without topic
                    openai_api.setQueryText(update.message.text)
                    response = openai_api.getResponse()
                if response != "":
                    await update.message.reply_text(response)
                return self.CHAT
        else:
            await update.message.reply_text("You are not in the valid users list!")
        return ConversationHandler.END

# -------------------------------------------------------------------------------------

if __name__ == "__main__":
    config = Config()
    openai_api = OpenaAI_API(config.openai_key)
    chatGPT_bot = ChatGPTBot(config, openai_api)
    chatGPT_bot.run()
