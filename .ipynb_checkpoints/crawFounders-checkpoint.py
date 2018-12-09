# coding=utf-8
# crawFounders.py
from urllib import request, parse
from bs4 import BeautifulSoup
from pymongo import MongoClient
from bson import ObjectId
import datetime
import ssl
import re
import time
import random

ssl._create_default_https_context = ssl._create_unverified_context  # 全局取消网页安全验证


class crawfounders:
    client = MongoClient('localhost', 27017)
    db = client.moniter_crowdfunding
    def __init__(self):
        self.Host = 'z.jd.com'
        self.User_Agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:60.0) Gecko/20100101 Firefox/60.0'
        self.hrefs = {'支持项目': 'http://z.jd.com/f/my_support.action?',
                    '关注项目': 'http://z.jd.com/f/my_focus.action?', 
                    '发起项目': 'http://z.jd.com/f/my_project.action?'}
        
        self.project = self.db.projects
        self.f_project = self.db.failure_projects
        self.p_founder = self.db.founders  
        
    def checkOtherCols(self):  # 往p_founders中插入第一批数据
        suc_ids = list(set(x['_id'] for x in self.project.find({}, projection={'_id':1})))
        for p_id in suc_ids[::-1]:
            if isinstance(p_id, ObjectId):
                print(f"success {p_id}")
                t_id = self.project.find_one({"_id":p_id}, projection={'项目编号':1})
                suc_ids.remove(p_id)
                suc_ids.append(t_id['项目编号'])
        
        fail_ids = list(set(x['详细信息']['_id'] for x in self.f_project.find({}, projection={'详细信息._id':1})))
        for p_id in fail_ids[::-1]:  # 将_id为ObjectID类型的替换为项目编号
            if isinstance(p_id, ObjectId):
                print(f"failure {p_id}")
                t_id = self.f_project.find_one({"详细信息._id":p_id}, projection={"详细信息.项目编号":1})
                fail_ids.remove(p_id)
                fail_ids.append(t_id["详细信息"]["项目编号"])
                
        return set(suc_ids) | set(fail_ids)
    
    def crawData(self, href, p_id):  # 爬取数据
        post_data = parse.urlencode({"flag":"2", "id":p_id})
        req = request.Request(href)
        req.add_header('User-Agent', self.User_Agent)
        req.add_header('Referer', f'http://z.jd.com/funderCenter.action?{post_data}')
        req.add_header('Host', self.Host)
        with request.urlopen(req, data=post_data.encode('utf-8')) as f:
            raw_html = f.read().decode()

        return raw_html

    def soupData(self, raw):  # 解析数据
        h_soup = BeautifulSoup(raw, 'html.parser')
        cat_div = h_soup.find('div', {'class': 'tab_cont db'})
        p_d = re.compile('(\d+)')
        c_dict = {}
        if cat_div:
            for x in cat_div.findAll('li'):
                prj_href = str(x).split("'")[1]
                prj_id = p_d.findall(prj_href)[0]
                c_dict[prj_id] = {'prj_name': x.p.string, 'prj_desc': x.a.string, 'prj_href': prj_href}

        return c_dict

    def insertData(self, p_id):  # 插入1个文档
        item = {'_id': p_id}
        try:
            for key in self.hrefs:
                raw = self.crawData(self.hrefs[key], item['_id'])
                c_dict = self.soupData(raw)
                item[key] = c_dict
            self.p_founder.insert_one(item)
            return 1
        except Exception as e:
            print(f"{p_id}插入失败!提示:{e}")
            return 0

    def insertDataSet(self, p_ids):  # 插入文档集合
        print(f"  计划插入{len(p_ids)}个文档")
        inserted, notInserted = [], []
        for p_id in p_ids:
            if self.insertData(p_id):
                inserted.append(p_id)
            else:
                notInserted.append(p_id)
        print(f" 实际插入{len(inserted)}个文档")
        return inserted, notInserted

    def getNewIDs(self):  # 下一步需要爬取的ids
        now_ids = []
        new_res = []
        for x in self.p_founder.find({}):
            temp = list(x['支持项目'].keys()) + list(x['关注项目'].keys()) + list(x['发起项目'].keys())
            now_ids.append(x['_id'])
            new_res.extend(temp)

        return set(new_res) - set(now_ids)

    def main(self):
        num_ids = self.p_founder.count_documents({})  # 查看集合p_founder中的文档数是否为0
        if not num_ids:
            ids = self.checkOtherCols()
            self.insertDataSet(ids)
            
        j = 1
        while True:
            time.sleep(10)
            print(f"第{j}轮")
            newIDs = self.getNewIDs()
            if newIDs:
                inserted, notinserted = self.insertDataSet(newIDs)
                j += 1
            else:
                break
            
if __name__ == '__main__':
    craw = crawfounders()
    craw.main()
