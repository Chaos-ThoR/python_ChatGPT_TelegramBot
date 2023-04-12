#!/usr/bin/python3
# -*- coding: utf-8 -*-

# pip3 install openai python-telegram-bot

import os
import sys
import json
import openai
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, error
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
    def __init__(self, name: str, id: int, path: str, max_entries, lang: str) -> None:
        self.name = name
        self.id = id
        self.path = path
        self.max_entries = max_entries
        self.data = None

    def save(self) -> None:
        with open(self.path, 'w') as outfile:
                        json.dump(self.data, outfile, indent=4)
    
    def lang(self) -> str:
        return self.data['language']

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
        self.openai_key = config['openai_key']
        self.telegram_token = config['telegram_token']
        self.max_history_entries = config['max_history_entries']
        models = []
        for model in config['models']:
            models.append(model)
        self.models = set(models)
        self.current_model = config['current_model']
        self.users = []
        for user in config['users']:
            if user:
                values = user.split("#")
                path = './chats/topics_{}.json'.format(values[1])
                user = User(values[1], values[0], path, self.max_history_entries * 2, values[2])
                self.users.append(user)

                # setup some filesystem operations
                if not os.path.exists(path):
                    json_data = {"language": "en", "current_topic": "", "topics": []}
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

    def saveCurrentModel(self) -> None:
        data = self._loadFile()
        if data['current_model'] != self.current_model:
            data['current_model'] = self.current_model
            configFile = open("config.json", "w")
            configFile.write(json.dumps(data, indent=4))
            configFile.close()

# -------------------------------------------------------------------------------------

class Translations:
    def __init__(self) -> None:
        self.translations_data = self._loadFile()
        self.translations = [{}]
        for obj in self.translations_data['tokens']:
            for key in obj:
                self.translations.append({key: obj[key]})

    def _loadFile(self):
        # load the configuration ..
        try:
            translation_data = open("translations.json", encoding='utf-8-sig')
            config = json.load(translation_data)
            translation_data.close()
            return config
        except IOError:
            print("Could not read translations file!")
            sys.exit()
        except json.JSONDecodeError:
            print("config.json: decode error!")
            sys.exit()
    
    def trans(self, token: str, lang : str) -> str:
        lang_index = 0 # 'en' as fallback
        for avail_lang in self.translations_data['lang']:
            if lang == avail_lang['key']:
                lang_index = lang['val']
        return self.translations[token][lang_index]
    
    def allTransAsRegex(self, token: str) -> str:
        for obj in self.translations:
            for key in obj:
                if key == token:
                    regEx_val = "^("
                    for value in obj[key]:
                        regEx_val += value + "|"
                    regEx_val = regEx_val[:-1] + ")$"
                    return regEx_val
    
    def langCount(self) -> int:
        for obj in self.translations:
            for key in obj:
                return len(obj[key])

# -------------------------------------------------------------------------------------

class OpenaAI_API:
    def __init__(self, config: Config) -> None:
        self.config = config
        openai.api_key = config.openai_key
        self.query = [{"role": "user", "content": ""}]

    def setModel(self, new_model: str) -> None:
        models = openai.Model.list()
        if new_model in models['data']:
            self.config.current_model = new_model
            self.config.saveCurrentModel()

    def setQueryText(self, text: str) -> None:
        self.query[0]['content'] = text

    def getResponse(self) -> str:
        try:
            completion = openai.ChatCompletion.create(model=self.config.current_model, messages=self.query)
            return completion.choices[0].message.content
        except openai.error.RateLimitError as ex:
            return ex._message
        finally:
            self.query[0]['content'] = ""
    
    def getAvailableModels(self) -> set:
        models = openai.Model.list()
        models_list = []
        for model in models['data']:
            models_list.append(model.id)
        models_set = set(models_list)
        available_models = models_set.intersection(config.models)
        return available_models
    
    def getImage(self) -> str:
        try:
            generation_response = openai.Image.create(prompt=self.query[0]['content'], n=1, size="1024x1024", response_format="url")
            return generation_response["data"][0]["url"] # extract image URL from response
        except openai.error.RateLimitError as ex:
            return ex._message
        finally:
            self.query[0]['content'] = ""

    def getTranscription(self, audio_file) -> str:
        try:
            transcription = openai.Audio.transcribe(audio_file)
            pass
        except openai.error.RateLimitError as ex:
            return ex._message
        return ""

# -------------------------------------------------------------------------------------

class ChatGPTBot:
    def __init__(self, config : Config, openaiAPI : OpenaAI_API, languages: Translations) -> None:
        self.config = config
        self.openai_api = openaiAPI
        self.lang = languages
        self.updater = Application.builder().token(self.config.telegram_token).build()

        # add event handlers..
        self.updater.add_handler(CommandHandler('h', self.help))
        self.updater.add_handler(CommandHandler('help', self.help))
        self.updater.add_handler(CommandHandler('hilfe', self.help))
        self.updater.add_handler(CommandHandler('start', self.start))

        # conversations
        # topic conversation
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

        # model conversation
        self.MODELSELECT, self.MODELSELECTED = range(2)
        model_handler = ConversationHandler(
            entry_points = [CommandHandler("model", self.model)],
            states = {
                self.MODELSELECT: [
                    MessageHandler(filters.Regex("^Modell wählen$"), self.setmodel),
                    MessageHandler(filters.Regex("^zeige aktuelles Modell$"), self.showmodel)
                ],
                self.MODELSELECTED: [
                    MessageHandler(filters.Regex(".*"), self.setnewmodel)
                ]
            }, fallbacks=[CommandHandler("cancel", self.cancel)])
        self.updater.add_handler(model_handler)

        # chat conversation
        self.CHAT = range(1)
        chat_handler = ConversationHandler(
            entry_points = [CommandHandler('chat', self.chat_query)],
            states = {
                self.CHAT: [
                    MessageHandler(filters.Regex(".*"), self.chat_query)
                ]
            }, fallbacks=[CommandHandler("cancel", self.cancel)])
        self.updater.add_handler(chat_handler)

        # image creation conversation
        self.CREATEIMAGE = range(1)
        image_handler = ConversationHandler(
            entry_points = [CommandHandler('image', self.image)],
            states = {
                self.CREATEIMAGE: [
                    MessageHandler(filters.Regex(".*"), self.create_image)
                ]
            }, fallbacks=[CommandHandler("cancel", self.cancel)])
        self.updater.add_handler(image_handler)
        
    async def topic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        if user:
            reply_keyboard = []
            reply_keyboard.append(["neues Thema"])
            reply_keyboard.append(["vorhandenes Thema"])
            reply_keyboard.append(["ohne Thema"])
            reply_keyboard.append(["zeige aktuelles Thema"])
            reply_keyboard.append(["lösche Thema"])
            reply_keyboard.append(["abbrechen"])
            try:
                await update.message.reply_text("Wie kann ich helfen?", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True))
            except error.NetworkError:
                self.updater = Application.builder().token(self.config.telegram_token).build()
                return self.topic(update, context)
        return self.SELECTION
        
    async def newtopic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            await update.message.reply_text("Thema?\nMöglichst als ein Wort!", reply_markup= ReplyKeyboardRemove())
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            return self.newtopic(update, context)
        return self.NEWTOPIC
    
    async def newtopicname(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        user.data['current_topic'] = update.message.text
        try:
            if update.message.text in user.topics():
                await update.message.reply_text("Thema existiert schon und ist jetzt aktiv!", reply_markup= ReplyKeyboardRemove())
            else:
                user.data['topics'].append({"name": update.message.text.strip(), "history": []})
                user.save()
                await update.message.reply_text("OK", reply_markup= ReplyKeyboardRemove())
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            return self.newtopicname(update, context)
        return ConversationHandler.END

    async def existingtopic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        reply_keyboard = []
        topics = user.topics()
        for topic in topics:
            reply_keyboard.append([topic])
        try:
            await update.message.reply_text("Deine Themen:", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True))
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            return self.existingtopic(update, context)
        return self.TOPICSELECTION

    async def setselectedtopic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        user.data['current_topic'] = update.message.text
        user.save()
        try:
            await update.message.reply_text("OK", reply_markup= ReplyKeyboardRemove())
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            return self.setselectedtopic(update, context)
        return ConversationHandler.END

    async def cleartopic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        user.data['current_topic'] = ""
        user.save()
        try:
            await update.message.reply_text("OK", reply_markup= ReplyKeyboardRemove())
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            return self.cleartopic(update, context)
        return ConversationHandler.END
    
    async def currenttopic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        try:
            if user.hasActiveTopic():
                await update.message.reply_text("aktuelles Thema:\n{}".format(user.data['current_topic']), reply_markup= ReplyKeyboardRemove())    
            else:
                await update.message.reply_text("aktuelles Thema:\n keines", reply_markup= ReplyKeyboardRemove())
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            return self.currenttopic(update, context)
        return ConversationHandler.END

    async def deletetopic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        reply_keyboard = []
        topics = user.topics()
        for topic in topics:
            reply_keyboard.append([topic])
        try:
            await update.message.reply_text("Deine Themen:", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True))
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            return self.deletetopic(update, context)
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
        try:
            await update.message.reply_text("OK", reply_markup= ReplyKeyboardRemove())
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            return self.deleteselectedtopic(update, context)
        return ConversationHandler.END
    
    async def model(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if self._isUser(update):
            reply_keyboard = []
            reply_keyboard.append(["zeige aktuelles Modell"])
            reply_keyboard.append(["Modell wählen"])
            try:
                await update.message.reply_text("Wähle?", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True))
            except error.NetworkError:
                self.updater = Application.builder().token(self.config.telegram_token).build()
                return self.model(update, context)
        return self.MODELSELECT
    
    async def showmodel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            await update.message.reply_text("Das aktuell verwendete Modell: {}".format(self.config.current_model), reply_markup= ReplyKeyboardRemove())
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            return self.showmodel(update, context)
        return ConversationHandler.END
    
    async def setmodel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        # create selection of models to choose from ..
        available_models = self.openai_api.getAvailableModels()
        reply_keyboard = []
        for model in available_models:
            reply_keyboard.append([model])
        try:
            await update.message.reply_text("Verfügbare Modelle:", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True))
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            return self.setmodel(update, context)
        return self.MODELSELECTED

    async def setnewmodel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        # set the new model for this bot
        self.openai_api.setModel(update.message.text)
        try:
            await update.message.reply_text("OK", reply_markup= ReplyKeyboardRemove())
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            return self.setnewmodel(update, context)
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            await update.message.reply_text("OK", reply_markup= ReplyKeyboardRemove())
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            return self.cancel(update, context)
        return ConversationHandler.END

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if self._isUser(update):
                await update.message.reply_text("Wilkommen beim ChatGPT Telegram Bot!")
            else:
                await update.message.reply_text("You are not in the valid users list!")
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            self.start(update, context)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if self._isUser(update):
                await update.message.reply_text("Wilkommen beim ChatGPT Telegram Bot!")
            else:
                await update.message.reply_text("You are not in the valid users list!")
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            self.help(update, context)

    async def chat_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            user = self.userById(update)
            if user:
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
                        self.openai_api.setQueryText(new_query_with_history)
                        response = self.openai_api.getResponse()
                        currentHistory.append(response)
                        user.updateHistory(currentTopic, currentHistory)
                        user.save()
                    else: # chat without topic
                        self.openai_api.setQueryText(update.message.text)
                        response = self.openai_api.getResponse()
                    if response != "":
                        await update.message.reply_text(response)
                    return self.CHAT
            else:
                await update.message.reply_text("You are not in the valid users list!")
        except error.NetworkError:
            self.updater = Application.builder().token(self.config.telegram_token).build()
            self.chat_query(update, context)
        return ConversationHandler.END
    
    async def image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        if user:
            await update.message.reply_text("Beschreibe das Bild..")
            return self.CREATEIMAGE
        else:
            await update.message.reply_text("You are not in the valid users list!")
            return ConversationHandler.END

    async def create_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = self.userById(update)
        self.openai_api.setQueryText(update.message.text)
        generated_image_url = self.openai_api.getImage()
        await self.updater.bot.send_photo(chat_id=user.id, photo=generated_image_url)
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
        return None

# -------------------------------------------------------------------------------------

if __name__ == "__main__":
    config = Config()
    languages = Translations()
    openai_api = OpenaAI_API(config)
    chatGPT_bot = ChatGPTBot(config, openai_api, languages)
    chatGPT_bot.run()
