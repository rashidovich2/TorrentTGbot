from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from torrent-client import downloading

# function to handle the /start command

log_time = 5


def start(update, context):
    update.message.reply_text('You can use this bot to download files from torrent')
    update.message.reply_text(main_menu_message(), reply_markup=main_menu_keyboard())


def main_menu_message():
    return 'Choose the option in main menu:'


def first_menu_message():
    return 'Choose the logging time:'


def second_menu_message():
    return 'Choose the option in main menu:'


def third_menu_message():
    return 'Choose the option in main menu:'


def fourth_menu_message():
    return 'Choose the option in main menu:'


def main_menu_keyboard():
    keyboard = [[InlineKeyboardButton('Change log_time', callback_data='m1')]]
    return InlineKeyboardMarkup(keyboard)


def main_menu(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        text=main_menu_message(),
        reply_markup=main_menu_keyboard())


def first_menu(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        text=first_menu_message(),
        reply_markup=first_menu_keyboard())


def first_menu_keyboard():
    keyboard = [[InlineKeyboardButton('5', callback_data='m3')],
                [InlineKeyboardButton('10', callback_data='m2')],
                [InlineKeyboardButton('20', callback_data='m4')],
                [InlineKeyboardButton('Main menu', callback_data='main')]]
    return InlineKeyboardMarkup(keyboard)


def second_menu_keyboard():
    keyboard = [[InlineKeyboardButton('Main menu', callback_data='main')]]
    return InlineKeyboardMarkup(keyboard)


def third_menu_keyboard():
    keyboard = [[InlineKeyboardButton('Main menu', callback_data='main')]]
    return InlineKeyboardMarkup(keyboard)


def fourth_menu_keyboard():
    keyboard = [[InlineKeyboardButton('Main menu', callback_data='main')]]
    return InlineKeyboardMarkup(keyboard)


def text(update, context):
    text_received = update.message.text
    update.message.reply_text(f'did you said "{text_received}" ?')


def downloader(update, context):
    name = update.message.document.file_name
    file_torrent = context.bot.getFile(update.message.document.file_id)
    file_torrent.download(name)

    # writing to a custom file
    with open(name, 'wb') as f:
        context.bot.get_file(update.message.document).download(out=f)
    global log_time
    update.message.reply_text('File uploaded!')
    fl = downloading(name, update, log_time)


def log_time_5(update, context):
    global log_time
    log_time = 5

    print(log_time)
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        text=second_menu_message(),
        reply_markup=second_menu_keyboard())


def log_time_10(update, context):
    global log_time
    log_time = 10

    print(log_time)
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        text=third_menu_message(),
        reply_markup=third_menu_keyboard())


def log_time_20(update, context):
    global log_time
    log_time = 20

    print(log_time)
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        text=fourth_menu_message(),
        reply_markup=fourth_menu_keyboard())


def error(update, context):
    print(f'Update {update} caused error {context.error}')


def main():
    TOKEN = "2007164030:AAEhuQkk3Y_uHBdXBKpdQOjdw3Yz6CiqU6M"
    # create the updater, that will automatically create also a dispatcher and a queue to
    # make them dialoge
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    # add handlers for start and help commands
    dispatcher.add_handler(CommandHandler("start", start))
    # add an handler for normal text (not commands)

    dispatcher.add_handler(MessageHandler(Filters.text, text))
    dispatcher.add_handler(CallbackQueryHandler(main_menu, pattern='main'))
    dispatcher.add_handler(CallbackQueryHandler(first_menu, pattern='m1'))
    dispatcher.add_handler(CallbackQueryHandler(log_time_5, pattern='m3'))
    dispatcher.add_handler(CallbackQueryHandler(log_time_10, pattern='m2'))
    dispatcher.add_handler(CallbackQueryHandler(log_time_20, pattern='m4'))
    dispatcher.add_handler(MessageHandler(Filters.document, downloader))
    dispatcher.add_error_handler(error)

    # start your shiny new bot
    updater.start_polling()
    # run the bot until Ctrl-C
    updater.idle()


if __name__ == '__main__':
    main()
