import requests
from bs4 import BeautifulSoup
import time
import re
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import json
from collections import OrderedDict
from pydantic import BaseModel
from tqdm import tqdm
import uvicorn


def preprocess(input_string):
    pattern = re.compile(r'\s지하|\S+로|\S*길|[^로길\s]번길|\d+\-?\d*|\S+[군구]|서울|부산|인천|대구|대전|광주|울산|세종|경기|강원|제주|충\w+북\S*|충\w+남\S*|전\w+북\S*|전\w+남\S*|경\w+북\S*|경\w+남\S*')
    result = pattern.findall(input_string)
    return ' '.join(result)


def trnslt(keywrd):
    client_id = "s9hk7dbizs"
    client_secret = "8BB4Py0QFxCgGhSZiNVsxGVgrk8LFuFkejrE4YRM"
    keywrd = keywrd[:round(len(keywrd)/2)] + re.sub(r'\S*[^\sa-zA-Z가-힣0-9-(),]+\S*', '', keywrd[round(len(keywrd)/2):])
    keywrd = re.sub(r'\S*동\S*|\(.*\)', '', keywrd.replace(u'GF', u'G/F').replace(u'지하', u'B'))

    data = {'text': keywrd,
            'source': 'en',
            'target': 'ko'}

    url = "https://naveropenapi.apigw.ntruss.com/nmt/v1/translation"

    header = {"X-NCP-APIGW-API-KEY-ID": client_id,
              "X-NCP-APIGW-API-KEY": client_secret}

    response = requests.post(url, headers=header, data=data)
    rescode = response.status_code
    if rescode != 200:
        return 'papago_err'
    else:
        send_data = response.json()
        trans_data = re.sub(r'\(.*\)|\d가','',send_data['message']['result']['translatedText']).replace(u'B', u' 지하').replace(u'G',u' 지하').replace(u'첨단과학기술로',u'첨단과기로')
        if ("B " in trans_data) or ("B," in trans_data) or (len(re.findall(r'B\d+',keywrd)) != 0):
            return f" {trans_data} 지하"
        else:
            return f" {trans_data}"


def srch(keywrd):
    if len(keywrd.replace(u'지하','').strip().split(' ')) <= 1:
        return '답 없음'
    base_url = f"https://www.juso.go.kr/support/AddressMainSearch.do?searchKeyword="
    session = requests.session()
    juso_response = session.get(f"{base_url}{keywrd}", timeout=999999)
    if juso_response.status_code != 200:
        return 'juso_err'
    else:
        try:
            soup = BeautifulSoup(juso_response.text, 'html.parser')
            count = soup.find('span', class_='count').get_text()
            if count == '0':
                return '답 없음'
            elif count != '1':
                addr_li_all = soup.find_all('li', class_='inner_addr')
                temp_addr = []
                for idx, addr in enumerate(addr_li_all):
                    temp_addr.append(re.sub(r'\(.*\)', '',
                                            addr.find('span', class_='roadNameText').get_text().replace(u'\xa0', ' ')))
                accept = []
                x = temp_addr[0].split(' ')
                for i in range(1, len(temp_addr)):
                    for j in x:
                        accept.append(temp_addr[i].find(j))
                if -1 in accept:
                    return '답 없음'
                else:
                    return addr_li_all[0].find('span', class_='roadNameText').get_text().replace(u'\xa0', ' ')
            else:
                addr_li = soup.find('li', class_='inner_addr')
                return addr_li.select_one('.roadNameText').get_text().replace(u'\xa0', u' ')
        except requests.exceptions.Timeout:
            time.sleep(0.1)


def trnsltNsrch(keywrd):
    return srch(preprocess(trnslt(keywrd)))

# ___________________________________________________________________


class Exception_(Exception):
    def __init__(self, name: str):
        self.name = name


class dataset(BaseModel):
    requestList: list


app = FastAPI()


@app.exception_handler(Exception_)
async def exception_handler(request: Request, exc: Exception_):
    return JSONResponse()


@app.get("/")
def home():
    return "home"


@app.post("/set_data/")
def post_data(data: dataset):
    temp = list(data.requestList)
    temp_list = []
    RESULT = OrderedDict()
    HEADER = OrderedDict()
    for item in tqdm(temp):
        Lower_result = OrderedDict()
        seq = item["seq"]
        a = trnsltNsrch(item["requestAddress"])
        if a == 'juso_err' or a == 'papago_err':
            result_code = "F"
            result_msg = f"seq {seq} is failed to transfer"
            HEADER["RESULT_CODE"] = result_code
            HEADER["RESULT_MSG"] = result_msg
            RESULT["HEADER"] = HEADER
            return json.dumps(RESULT, ensure_ascii=False)
        else:
            Lower_result["seq"] = seq
            Lower_result["resultAddress"] = a
            temp_list.append(Lower_result)
    print(len(temp_list))
    HEADER["RESULT_CODE"] = "S"
    print("header_resultcode ok")
    HEADER["RESULT_MSG"] = "Success"
    print("header_resultmsg ok")
    RESULT["HEADER"] = HEADER
    print("header ok")
    RESULT["BODY"] = temp_list
    print("body ok")
    return json.dumps(RESULT, ensure_ascii=False)
