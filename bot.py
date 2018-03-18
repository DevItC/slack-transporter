import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rq import Queue
from rq.job import Job
from worker import conn
import yaml
from slackclient import SlackClient



class SlackScraper:
    def __init__(self, username, password):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        self.driver = webdriver.Chrome(chrome_options=options)
        self.driver.get('https://devitconsultancy.slack.com')
        time.sleep(2)

        email = self.driver.find_element_by_id('email')
        email.send_keys(username)
        self.driver.find_element_by_id('password').send_keys(password)
        email.submit()

        wait = WebDriverWait(self.driver, 100)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'c-message')))
        self.latest_message = None


    def scrape(self):
        messages = self.driver.find_elements_by_class_name('c-message')
        parsed = []
        author_name = 'NA'
        author_id = 'NA'

        for message in messages:
            text = message.find_element_by_class_name('c-message__body').text
            timestamp_element = message.find_element_by_class_name('c-timestamp')
            timestamp = timestamp_element.find_element_by_tag_name('span').get_attribute('innerHTML')
            message_id = timestamp_element.get_attribute('href').split('/')[-1]
            item = {
                'message_id': message_id,
                'text': text,
                'timestamp': timestamp
            }

            author_elements = message.find_elements_by_class_name('c-message__sender_link')
            if len(author_elements) != 0:
                author_name = author_elements[0].text
                author_id = author_elements[0].get_attribute('href').split('/')[-1]
            
            item['author_name'] = author_name
            item['author_id'] = author_id
            parsed.append(item)

        ret = []
        try:
            while parsed[-1]['message_id'] != self.latest_message:
                ret.append(parsed.pop())
        except IndexError:
            pass
        try:
            self.latest_message = ret[0]['message_id']
        except IndexError:
            pass

        return ret[::-1]


def post_message(channel, message, slackclient):
    slackclient.api_call('chat.postMessage', channel = channel,
                        text = '{} [{}]: {}'.format(message['author_name'], message['timestamp'], message['text']))


def main():
    print('[*] Booting up...')
    with open('config.yaml') as f:
        config = yaml.load(f)
        username = config['CREDS']['USERNAME']
        password = config['CREDS']['PASSWORD']
        slack_token = config['SLACKAPI']['TOKEN']

    scraper = SlackScraper(username=username, password=password)
    q = Queue(connection=conn)
    sc = SlackClient(slack_token)
    print('[*] Running...')

    while True:
        messages = scraper.scrape()
        for message in messages:
            task = q.enqueue_call(func='scraper.post_message', args=('general', message, sc), result_ttl=5000, timeout=3600)



if __name__=='__main__':
    main()
