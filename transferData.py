# coding=utf-8
'''
author: Yu Xiao
Date: 2019/12/27
Function: 转换mongoDB数据为格式化数据
'''
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
import pandas as pd
import datetime
from bson import ObjectId
from pymongo import MongoClient
from scipy.optimize import minimize


class ItemDiffusion:
    def __init__(self, proj, diffu_col_names, front_page):
        self.proj = proj
        self.front_page = front_page
        self.diffu_col_names = diffu_col_names
        try:
            self.id = self.proj["_id"]
            self.name = self.proj["项目名称"]
            self.state = self.proj["状态"]
            self.duration = self.proj["众筹期限"]
            self.aim_fund = self.proj["目标金额"]
            self.final_fund = self.proj["项目动态信息"][-1]["筹集金额"]
            self.company_name = self.proj["公司名称"]
            self.company_phone = self.proj["公司电话"]
            self.link = self.proj["发起人链接"]
            self.category = self.proj["所属类别"]

            self.pure_diffu_df = self.get_pure_diffu()  # 未处理的扩散数据
            self.front_df = self.get_front_position()  # 首页数据
            self.diffu_df = self.merge_diffu_position()
            self.diffu_day_df = self.to_diffu_day_df()  # 每天最晚时间点的扩散数据
            self.cum_diffu_df = self.prepare_data()  # 索引为相对众筹开始时间点的间隔
        except Exception as e:
            print(e)

    def get_front_demo_data(self, a_dict, t_dict, pid):
        """
        递归获取时间序列t_dict。t_dict与a_dict键相对应，查看对应时期各监测时间点的各展区是否包含目标pid
        """
        for key in a_dict:
            if isinstance(a_dict[key], list):
                if pid in a_dict[key]:
                    t_dict[key] = t_dict.get(key, []) + [1]
                else:
                    t_dict[key] = t_dict.get(key, []) + [0]
            elif isinstance(a_dict[key], dict):
                t_dict[key] = self.get_front_demo_data(a_dict[key], {}, pid)
            elif key == "监测时间":
                t_dict[key] = t_dict.get(key, []) + [a_dict[key]]
            else:
                pass
        return t_dict

    def get_eff_data(self, t_dict, prev_keys=[], dataset={}):
        """
        递归获取t_dict对应压缩形式
        """
        for key in t_dict:
            if isinstance(t_dict[key], list):
                c_key = ">".join(prev_keys + [key]) if prev_keys else key
                dataset[c_key] = t_dict[key]
            else:
                dataset = self.get_eff_data(
                    t_dict[key], prev_keys + [key], dataset)
        return dataset

    def get_front_position(self):
        """
        获取众筹生命周期内在首页各位置出现时间的判断
        """
        # 项目扩散数据最早与最晚时间点
        t_start = self.proj['项目动态信息'][0]['爬取时间']
        t_end = self.proj['项目动态信息'][-1]['爬取时间'] + \
            datetime.timedelta(hours=8)
        # 取出这个时间段的主页观察数据
        f_page = self.front_page.find(
            {"监测时间": {"$gte": t_start, "$lte": t_end}}, sort=[("监测时间", 1)]
        )
        # 迭代查看_id是否存在各时间点的各展区
        t_dict = {}
        for a in f_page:
            t_dict = self.get_front_demo_data(a, t_dict, self.id)
        # 转换为DataFrame
        dataset = self.get_eff_data(t_dict)
        col_names = list(dataset)
        col_names.remove("监测时间")
        front_df = pd.DataFrame(
            dataset, index=dataset["监测时间"], columns=col_names)
        return front_df

    def get_pure_diffu(self):
        dyn_info = self.proj["项目动态信息"]
        # 剔除更新时间相同的记录
        records = {"更新时间": [], "星期": [], "支持者数": [],
                   "关注数": [], "点赞数": [], "完成百分比": [], "筹集金额": []}
        a1 = dyn_info[0]
        for a2 in dyn_info:
            if a2["更新时间"] != a1["更新时间"]:
                records["更新时间"].append(a2["更新时间"])
                # 0 -> monday, 1 -> tuesday, ..., 6 -> sunday
                records["星期"].append(records["更新时间"][-1].weekday())
                records["支持者数"].append(a2["支持者数"])
                records["关注数"].append(a2["关注数"])
                records["完成百分比"].append(a2["完成百分比"])
                records["筹集金额"].append(a2["筹集金额"])
                records["点赞数"].append(a2["点赞数"])

                a1 = a2

        df = pd.DataFrame(
            records, index=records["更新时间"], columns=self.diffu_col_names)
        return df

    def merge_diffu_position(self):
        """
        合并扩散数据和首页版面呈现时间数据
        """
        new_colNames = list(self.pure_diffu_df.columns) + \
            list(self.front_df.columns)
        new_index = self.pure_diffu_df.index
        new_values = []
        for i, idx1 in enumerate(self.pure_diffu_df.index):
            for j, idx2 in enumerate(self.front_df.index):
                if idx1 <= idx2:
                    new_values.append(
                        list(self.pure_diffu_df.iloc[i].values) + list(self.front_df.iloc[j].values))
                    break
            else:
                print(i, idx1)
        merge_data = pd.DataFrame(
            new_values, columns=new_colNames, index=new_index)
        return merge_data

    def to_diffu_day_df(self):  # 保留每天一个观测
        new_index = []
        for i in range(1, len(self.diffu_df.index)):
            a = self.diffu_df.index[i - 1]
            b = self.diffu_df.index[i]
            if (b.year, b.month, b.day) != (a.year, a.month, a.day):
                new_index.append(i - 1)
        return self.diffu_df.iloc[new_index]

    def prepare_data(self):  # 将时间转换为相对众筹开始的绝对时长
        data = self.diffu_day_df[self.diffu_day_df.index >=
                                 pd.Timestamp(self.proj["状态变换时间1-2"])]  # 众筹开始后的数据

        interv_list = [t - pd.Timestamp(self.proj["状态变换时间1-2"])
                       for t in data.index]
        # 转换为相对众筹开始时间的绝对时长(小时)
        t_list = list(
            map(lambda x: round(
                x.to_pytimedelta().total_seconds() / 3600, 1), interv_list)
        )
        data.index = t_list
        return data

    def increasement(self, x):  # 非累积采纳数量
        return [(x[i] - x[i - 1]) if i >= 1 else x[0] for i in range(len(x))]


class ItemReview:
    pass


if __name__ == "__main__":
    client = MongoClient("127.0.0.1", 27017)
    db = client.moniter_crowdfunding
    # db.authenticate(name="craw", password="craw")
    project = db.projects
    s_project = db.sucess_projects
    f_project = db.failure_projects
    front_page = db.front_page

    diffu_col_names = ["星期", "关注数", "支持者数", "点赞数", "完成百分比", "筹集金额"]
    proj = s_project.find_one({'项目动态信息.0.爬取时间': {'$gte': datetime.datetime(2019, 1, 1),
                                                 '$lte': datetime.datetime(2019, 1, 10)}})
    proj_diffu_data = ItemDiffusion(
        proj=proj, diffu_col_names=diffu_col_names, front_page=front_page)

    review_col_names = ["parentId", "topicId",
                        "topicConten", "createTime", "nicknameShow", "replys"]
