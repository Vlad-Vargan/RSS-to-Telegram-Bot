import feedparser
import logging
import sqlite3
import os
from telegram.ext import Updater, CommandHandler
from telegram.ext import CallbackContext

from telegram import Update

from pathlib import Path
from dotenv import load_dotenv


load_dotenv()


bot_token = os.getenv('TOKEN')
chat_id = os.getenv('CHATID')
delay = int(os.getenv('DELAY', 60))


Path("config").mkdir(parents=True, exist_ok=True)

rss_dict = {}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

# =========
# SQLITE
# =========


def sqlite_connect():
    global conn
    conn = sqlite3.connect('config/rss.db', check_same_thread=False)


def sqlite_load_all():
    sqlite_connect()
    c = conn.cursor()
    c.execute('SELECT * FROM rss')
    rows = c.fetchall()
    conn.close()
    return rows


def sqlite_write(name, link, last):
    sqlite_connect()
    c = conn.cursor()
    q = [(name), (link), (last)]
    c.execute('''INSERT INTO rss('name','link','last') VALUES(?,?,?)''', q)
    conn.commit()
    conn.close()


# RSS________________________________________
def rss_load():
    # if the dict is not empty, empty it.
    if bool(rss_dict):
        rss_dict.clear()

    for row in sqlite_load_all():
        rss_dict[row[0]] = (row[1], row[2])


def cmd_rss_list(update: Update, context: CallbackContext):
    if bool(rss_dict) is False:

        update.effective_message.reply_text("The database is empty")
    else:
        for title, url_list in rss_dict.items():
            update.effective_message.reply_text(
                "Title: " + title +
                "\nrss url: " + url_list[0] +
                "\nlast checked article: " + url_list[1])


def cmd_rss_add(update: Update, context: CallbackContext):
    # try if there are 2 arguments passed
    try:
        context.args[1]
    except IndexError:
        update.effective_message.reply_text(
            "ERROR: The format needs to be: /add title http://www.URL.com")
        raise
    # try if the url is a valid RSS feed
    try:
        rss_d = feedparser.parse(context.args[1])
        rss_d.entries[0]['title']
    except IndexError:
        update.effective_message.reply_text(
            "ERROR: The link does not seem to be a RSS feed or is not supported")
        raise
    sqlite_write(context.args[0], context.args[1],
                 str(rss_d.entries[0]['link']))
    rss_load()
    update.effective_message.reply_text(
        "added \nTITLE: %s\nRSS: %s" % (context.args[0], context.args[1]))


def cmd_rss_remove(update: Update, context: CallbackContext):
    conn = sqlite3.connect('config/rss.db')
    c = conn.cursor()
    q = (context.args[0],)
    try:
        c.execute("DELETE FROM rss WHERE name = ?", q)
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print('Error %s:' % e.args[0])
    rss_load()
    update.effective_message.reply_text("Removed: " + context.args[0])


def cmd_help(update: Update, context: CallbackContext):
    update.effective_message.reply_markdown_v2(
        "RSS to Telegram bot" +
        "\n\nAfter successfully adding a RSS link, the bot starts fetching the feed every "
        + str(delay) + " seconds\. \(This can be set\)" +
        "\n\nTitles are used to easily manage RSS feeds and need to contain only one word" +
        "\n\ncommands:" +
        "\n/help Posts this help message" +
        "\n/add title http://www\.RSS\-URL\.com" +
        "\n/remove \!Title\! removes the RSS link" +
        "\n/list Lists all the titles and the RSS links from the DB" +
        "\n/test Inbuilt command that fetches a post from Reddits RSS\." +
        "\n\nThe current chatId is: " + str(update.message.chat.id) +
        "\n\nIf you like the project, star it on [DockerHub](https://hub.docker.com/r/bokker/rss.to.telegram)")


def rss_monitor(context: CallbackContext):
    for name, url_list in rss_dict.items():
        rss_d = feedparser.parse(url_list[0])
        if (url_list[1] != rss_d.entries[0]['link']):
            conn = sqlite3.connect('config/rss.db')
            q = [(name), (url_list[0]), (str(rss_d.entries[0]['link']))]
            c = conn.cursor()
            c.execute(
                '''INSERT INTO rss('name','link','last') VALUES(?,?,?)''', q)
            conn.commit()
            conn.close()
            rss_load()
            rss_post = rss_d.entries[0]['title'] + "\n\n" + rss_d.entries[0]['link']
            context.bot.send_message(chat_id, rss_post)


def cmd_test(update: Update, context: CallbackContext):
    url = "https://feeds.feedburner.com/visualcapitalist"
    rss_d = feedparser.parse(url)

    update.effective_message.reply_text(
        "<b>" + rss_d.entries[0]['title'] + "</b>"
        + "\n"
        + "<i>" + rss_d.entries[0]['summary_detail']["value"].split("</p>")[0].replace("<p>", "") + "</i>"
        + "\n\n"
        + rss_d.entries[0]['link']
    , parse_mode="HTML")


def init_sqlite():
    conn = sqlite3.connect('config/rss.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE rss (name text, link text, last text)''')


def main():
    updater = Updater(token=bot_token, use_context=True)
    job_queue = updater.job_queue
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("add", cmd_rss_add))
    dp.add_handler(CommandHandler("help", cmd_help))
    dp.add_handler(CommandHandler("test", cmd_test, ))
    dp.add_handler(CommandHandler("list", cmd_rss_list))
    dp.add_handler(CommandHandler("remove", cmd_rss_remove))

    # try to create a database if missing
    try:
        init_sqlite()
    except sqlite3.OperationalError:
        pass
    rss_load()

    job_queue.run_repeating(rss_monitor, delay)

    updater.start_polling()
    updater.idle()
    conn.close()


if __name__ == '__main__':
    main()
