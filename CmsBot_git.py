# -*- coding: utf-8 -*-
import logging
import MySQLdb
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
import ComplaintClassifier

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

db = MySQLdb.connect(user="root", passwd="12345", db="cms", use_unicode=True)
CHOOSING, CHOOSING_COMM, TEXT, PHOTO, LOCATION, VIEWALL = range(6)

# noinspection SqlNoDataSourceInspection,SqlResolve
class CmsBot:

    def __init__(self):
        self.classifier = ComplaintClassifier.ComplaintClassifier()
        API_key = ''
        self.updater = Updater(API_key, use_context=True)
        self.dp = self.updater.dispatcher

        self.conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],

            states={
                CHOOSING: [MessageHandler(Filters.regex('^Создать новое обращение$'), self.request_text),
                           MessageHandler(Filters.regex('^Проверить или изменить мои обращения в системе$'),
                                          self.view_all_tickets)],

                TEXT: [MessageHandler(Filters.text, self.text)],

                PHOTO: [MessageHandler(Filters.photo, self.photo),
                        MessageHandler(Filters.regex('^(Без фото)$'), self.skip_photo)],

                LOCATION: [MessageHandler(Filters.location, self.location),
                           MessageHandler(Filters.regex('^(Без геометки)$'), self.skip_location)]
            },

            fallbacks=[CommandHandler('cancel', self.cancel)]
        )

        self.comments_hadler = ConversationHandler(
            entry_points=[MessageHandler(Filters.regex('\d+'), self.show_comments)],

            states={
                CHOOSING_COMM: [MessageHandler(Filters.text, self.add_comment)],
            },

            fallbacks=[CommandHandler('cancel', self.cancel)]
        )

        self.dp.add_handler(self.conv_handler)
        self.dp.add_handler(self.comments_hadler)

        self.dp.add_handler(CommandHandler("help", help))
        self.dp.add_error_handler(self.error)
        self.updater.start_polling()
        self.updater.idle()

    def check_user_exists(self, user_id):
        c = db.cursor()
        c.execute("""SELECT * FROM user WHERE user_id = %s""", (user_id,))
        c.fetchone()
        if c.rowcount > 0:
            c.close()
            return True
        else:
            c.close()
            logger.info("userID %s does not exists", user_id)
            return False

    def insert_new_user(self, user):
        c = db.cursor()
        c.execute("""INSERT INTO cms.user (user_id, FIO) VALUES (%s, %s)""", (user.id, user.first_name,))
        db.commit()
        if c.rowcount > 0:
            logger.info("user inserted")
        else:
            logger.info("user inserting failed")
        c.close()

    def get_department_id(self, ticketText):
        department_name = self.classifier.predict(ticketText)[0]
        print(department_name)
        c = db.cursor()
        c.execute('SET NAMES utf8mb4')
        c.execute("SET CHARACTER SET utf8mb4")
        c.execute("SET character_set_connection=utf8mb4")
        c.execute("""SELECT department_id FROM department WHERE department.name = %s""",
                  (department_name.encode('utf-8'),))
        if c.rowcount > 0:
            department_id = c.fetchone()[0]
            c.close()
            logger.info("Department ID: %s", department_id)
            return department_id, department_name
        else:
            print('problems')

    def start(self, update, context):
        keyboard = [["Создать новое обращение"],
                    ["Проверить или изменить мои обращения в системе"]]
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        update.message.reply_text('Здравствуйте! Что вы хотите сделать? (отменить действие - команда /cancel)',
                                  reply_markup=markup)
        return CHOOSING

    def request_text(self, update, context):
        update.message.reply_text("Пожалуйста, отправьте текст обращения")
        return TEXT

    def text(self, update, context):
        user = update.message.from_user
        ticketText = update.message.text.encode('utf-8')
        department_id, department_name = self.get_department_id(ticketText)
        context.chat_data['dept_id'] = department_id
        context.chat_data['dept_name'] = department_name
        if not (self.check_user_exists(user.id)):
            self.insert_new_user(user)
        c = db.cursor()
        c.execute('SET NAMES utf8mb4')
        c.execute("SET CHARACTER SET utf8mb4")
        c.execute("SET character_set_connection=utf8mb4")
        try:
            c.execute("""INSERT INTO cms.ticket (author_id, department_id, text) VALUES (%s, %s, %s)""",
                      (user.id, department_id, ticketText,))
        except (MySQLdb.Error, MySQLdb.Warning) as e:
            print(e)
        context.chat_data['ticket_id'] = c.lastrowid
        db.commit()
        c.close()
        keyboard = [["Без фото"]]
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        update.message.reply_text("Добавьте фото при необходимости",
                                  reply_markup=markup)
        return PHOTO

    def photo(self, update, context):
        user = update.message.from_user
        photo_file = update.message.photo[-1].get_file()
        logger.info("Photo of %s: %s", user.first_name, 'user_photo.jpg')
        keyboard = [["Без геометки"]]
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        update.message.reply_text("Файл получен. Прикрепите геометку при необходимости", reply_markup=markup)
        return LOCATION

    def skip_photo(self, update, context):
        user = update.message.from_user
        logger.info("User %s did not send a photo.", user.first_name)
        keyboard = [["Без геометки"]]
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        update.message.reply_text("Прикрепите геометку при необходимости", reply_markup=markup)
        return LOCATION

    def location(self, update, context):
        user_location = update.message.location
        c = db.cursor()
        try:
            c.execute("""UPDATE ticket SET geotag_lat = %s, geotag_long = %s WHERE ticket_id = %s""",
                      (user_location.latitude, user_location.longitude, context.chat_data['ticket_id'],))
        except (MySQLdb.Error, MySQLdb.Warning) as e:
            print(e)
        update.message.reply_text(
            'Геолокация добавлена. Спасибо! Ваше обращение принято. Номер обращения: ' +
            context.chat_data['ticket_id'].__str__() + ", ответственный департмент: " + context.chat_data['dept_name'] +
            ". Для начала работы наберите команду /start", reply_markup=ReplyKeyboardRemove())
        db.commit()
        c.close()
        return ConversationHandler.END

    def skip_location(self, update, context):

        message = 'Спасибо! Ваше обращение принято. Номер обращения: {0}, Ответственный орган: {1}. ' \
                  'Для начала работы наберите команду /start'.format(context.chat_data['ticket_id'], context.chat_data['dept_name'])
        update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    def view_all_tickets(self, update, context):
        c = db.cursor()
        c.execute("""SELECT CAST(CONVERT(ticket_id USING utf8) AS binary), 
                            CAST(CONVERT(status USING utf8) AS binary), 
                            CAST(CONVERT(department.name USING utf8) AS binary)
                            FROM ticket, department 
                            WHERE author_id = %s AND department.department_id = ticket.department_id""",
                  (update.message.from_user.id,))
        result = ""
        keyboard = []
        for ticket in c:
            result = result + "ID: " + ticket[0].decode('utf-8') + \
                     ", статус: " + ticket[1].decode('utf-8') + \
                     ", отв. департамент: " + ticket[2].decode('utf-8') + "\n"
            keyboard.append([ticket[0].decode('utf-8')])
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        update.message.reply_text("Ваши обращения: \n" + result +
                                  "\n Чтобы посмотреть комментарии, нажмите на кнопку нужного обращения. "
                                  "Для возврата в меню отправьте команду /start", reply_markup=markup)
        c.close()
        return ConversationHandler.END

    def show_comments(self, update, context):
        ticket_id = update.message.text
        context.chat_data['ticket_id'] = ticket_id
        c = db.cursor()
        c.execute('SET NAMES utf8mb4')
        c.execute("SET CHARACTER SET utf8mb4")
        c.execute("SET character_set_connection=utf8mb4")
        c.execute("""SELECT CAST(CONVERT(comment.text USING utf8) AS binary),
                            CAST(CONVERT(user.FIO USING utf8) AS binary) 
                            FROM comment, user, ticket 
                            WHERE comment.ticket_id = %s AND
                            comment.author_id = user.user_id AND 
                            ticket.author_id = %s""", (ticket_id, update.message.from_user.id))
        result = ''
        if c.rowcount > 0:
            for comment in c:
                result = result + comment[1].decode('utf-8') + ": " + comment[0].decode('utf-8') + "\n"
        else:
            result = 'Комментариев еще нет'
        update.message.reply_text("Комментарии к обращению " + ticket_id + ":\n" + result +
                                  "\nОтправьте текст нового комментарий, либо для отмены /cancel")
        c.close()
        return CHOOSING_COMM

    def add_comment(self, update, context):
        comment = update.message.text.encode('utf-8')
        c = db.cursor()
        c.execute('SET NAMES utf8mb4')
        c.execute("SET CHARACTER SET utf8mb4")
        c.execute("SET character_set_connection=utf8mb4")
        try:
            c.execute("""INSERT INTO cms.comment (author_id, ticket_id, text) VALUES (%s, %s, %s)""",
                      (update.message.from_user.id, context.chat_data['ticket_id'], comment,))
        except (MySQLdb.Error, MySQLdb.Warning) as e:
            print(e)
        db.commit()
        c.close()
        update.message.reply_text("Комментарий успешно добавлен. Для возврата в меню отправьте команду /start")
        return ConversationHandler.END

    def cancel(self, update, context):
        update.message.reply_text('Действие отменено. Для начала работы наберите команду /start', reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    def help(self, update, context):
        help = 'Бот позволяет работать с обращениями в городскую администрацию. ' \
               'Для начала работы наберите команду /start и следуйте дальнейшим инструкциям.' \
               'Отменить текущее действие в любой момент - команда /cancel. ' \
               'Получить справку - команда /help.'
        update.message.reply_text(help)

    def error(self, update, context):
        logger.warning('Update "%s" caused error "%s"', update, context.error)

