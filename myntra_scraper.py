import re
import time
import json
import pickle
import requests
import pandas as pd
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from chromedriver_py import binary_path
import undetected_chromedriver as uc
from fake_useragent import UserAgent
import gzip, pickle
import os
import shutil
from bs4 import BeautifulSoup
# chrome_version = "114.0.5735.90" 
# chrome_driver_url = f"https://chromedriver.storage.googleapis.com/{chrome_version}/chromedriver_win32.zip"


class Zaubacorp:
    def __init__(self):
        options = uc.ChromeOptions() 
        options.headless=False
        self.driver = uc.Chrome(use_subprocess=True,executable_path=r"chromedriver.exe",option=options)
        self.ua = UserAgent()
        self.filters_list=[]
        self.prod_details_list=[]
        try:
            with open('products-data.pkl', 'rb') as fp:
                self.prod_details_list = pickle.load(fp)
                print(self.prod_details_list[0])
        except FileNotFoundError:
            print('No cached data found')
        self.worker_count = 1

    def start_scraping(self, filters_list,start_page, end_page):
        self.filters_list=filters_list
        self.get_catalog_info(start_page, end_page)
        time.sleep(2)
        self.get_product_data()
        df = pd.DataFrame(self.product_details)
        df.to_csv('prod-details.csv')
        df.to_excel('prod-details.xlsx')

    def get_catalog_info(self, start_page, end_page):
        print(start_page," ",end_page)
        temp_file = 'temp_product-data.pkl'
        for filter in self.filters_list:
            
            self.driver.get(f"https://www.myntra.com/{filter}")
            end_page=self.driver.find_element(By.XPATH,'//*[@id="mountRoot"]//li[@class="pagination-paginationMeta"]')
            matches=re.findall('\d+',end_page.text)
            if len(matches) >= 2:
                end_page = matches[1]
                print(end_page)
            else:
                continue
            try:
                for page_number in range(start_page, end_page):

                    url=f"https://www.myntra.com/{filter}/"
                    self.driver.get(f"https://www.myntra.com/{filter}?p={page_number}")

                    prod_item =[href_val.get_attribute('href') for href_val in self.driver.find_elements(By.XPATH, '//*[@id="mountRoot"]//a[@data-refreshpage="true"]')]
                    prod_item=self.prepare_data(prod_item,filter)
                    self.prod_details_list.extend(prod_item)
                    with open(temp_file, "wb") as temp_fp:
                        pickle.dump(self.prod_details_list,temp_fp)
                    print('Product Details Fetched till ', page_number, 'page')
            except Exception as e:
                with open('error.txt', 'a') as f:
                    f.write(str(page_number) + '\n')
                    f.write(str(e) + '-------------------------\n')
                print('Error at page number', page_number, '\n', 'Error : ', str(e))
            if os.path.exists('products-data.pkl'):
                shutil.copy(temp_file, 'products-data.pkl')
            else:
                with open("products-data.pkl", "wb") as fin_fp:
                    shutil.copy(temp_file, 'products-data.pkl')
        print('Çlosing Driver')

    def get_product_data(self):
        headers = {
            'Cookie': 'drupal.samesite=1',
            'User-Agent': self.ua.random
        }
        print('Started Product Detail Extraction Function')
        def process_product_item(product):
            # response = requests.request("GET", product['product_url'], headers=headers)
            # product_update = self.extract_prod_data(response.text)
            product_update = self.extract_prod_data(product['product_url'])
            product.update(product_update)
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.worker_count) as executor:
            futures = [executor.submit(process_product_item, prod) for prod in self.prod_details_list]
            concurrent.futures.wait(futures)
        # print("dsfsdgasdg",self.prod_details_list[:1][0])
        # process_product_item(self.prod_details_list[:1][0])
        df = pd.DataFrame(self.prod_details_list)
        # df = df.drop_duplicates(subset=['cin'])
        df.to_csv('prod-details-safety-backup.csv')
        df.to_excel('prod-details-safety-backup.xlsx')
    

        

    @staticmethod
    def prepare_data(product_elements,filter):
        current_page_product_data    = []
        for prod in product_elements:

            item_data = {
                "product_general_category":re.search(r'myntra\.com/([^/]+)', prod).group(1) if re.search(r'myntra\.com/([^/]+)', prod) else None,
                "product_filter_category":filter,
                "product_url": prod,
                "brand":"",
                "product_name":"" ,
                "image_urls": [],
                "sizes":[],
                "product_details":"",
                "product_material_n_fit":[],
            }
            current_page_product_data.append(item_data)
        return current_page_product_data

    @staticmethod
    def save_data(filename, data):
        with open(filename, "w") as outfile:
            outfile.write(str(data))
    
    # @staticmethod
    def extract_prod_data(self, url):
        print(url)
        self.driver.get(url)
        product_name = self.driver.find_element(By.XPATH, '//*[@id="mountRoot"]//h1[@class="pdp-name"]').text.strip() if self.driver.find_element(By.XPATH,'//h1[@class="pdp-name"]') else None    
        brand_name = self.driver.find_element(By.XPATH,'//h1[@class="pdp-title"]').text.strip() if self.driver.find_element(By.XPATH,'//h1[@class="pdp-title"]') else None    
        image_elements = self.driver.find_elements(By.XPATH, '//*[@class="image-grid-image"]')
        image_urls=[]
        for element in image_elements:
            style_attribute = element.get_attribute('style')
            if style_attribute:
                match = re.search(r'url\("([^"]+)"\)', style_attribute)
                if match:
                    image_url = url = match.group(1)
                    image_urls.append(image_url)

        sizes = [size_element.text.strip() for size_element in self.driver.find_elements(By.XPATH, '//*[contains(@class, "size-buttons-unified-size")]')]
        prod_details = self.driver.find_element(By.XPATH, '//*[@class="pdp-product-description-content"]').text.strip()
        prod_extradata = [p.text.strip() for p in self.driver.find_elements(By.XPATH, '//*[@class="pdp-sizeFitDescContent pdp-product-description-content"]')]
        output={
            "brand":brand_name,
            "product_name":product_name,
            "image_urls":image_urls,
            "sizes":sizes,
            "product_details":prod_details,
            "product_material_n_fit":prod_extradata,
        }
        # print(output)
        time.sleep(1)
        return output



    

if __name__ == "__main__":
    # filters_string = input("Enter a list of filters (most likely roc. eg: RoC-Delhi RoC-Mumbai) (space or comma-separated): ")
    # filters_list = [s.strip() for s in re.split(r'[,\s]+', filters_string)]
    filters_list=["men-casual-shirts"]
    zaubacorp_obj = Zaubacorp()
    zaubacorp_obj.start_scraping(filters_list,1,1)
# zaubacorp_obj.get_company_emails()

# start_page = 1                 start_page = 2
# //*[@id="table"]/tbody/tr[1]   //*[@id="table"]/tbody/tr[1]
# //*[@id="table"]/tbody/tr[2]   //*[@id="table"]/tbody/tr[2]
# .
# .
# .
# //*[@id="table"]/tbody/tr[30]

# //*[@id="block-system-main"]/div[2]/div[1]/text()[4]
# //*[@id="block-system-main"]/div[2]/div[1]/text()[4]

# Email Xpath : //*[@id="block-system-main"]/div[2]/div[1]/div[5]/div/div[1]/p[1]/text()
