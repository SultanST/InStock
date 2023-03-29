#!/usr/local/bin/python3
# -*- coding: utf-8 -*-


import logging
import concurrent.futures
import pandas as pd

import os.path
import sys
# 在项目运行时，临时将项目路径添加到环境变量
cpath = os.path.dirname(os.path.dirname(__file__))
sys.path.append(cpath)

import libs.run_template as runt
import libs.tablestructure as tbs
import libs.database as mdb
from libs.singleton import stock_hist_data
import kline.pattern_recognitions as kpr

__author__ = 'myh '
__date__ = '2023/3/10 '


def prepare(date):
    try:
        stocks_data = stock_hist_data(date=date).get_data()
        if stocks_data is None:
            return
        results = run_check(stocks_data, date=date)
        if results is None:
            return

        table_name = tbs.TABLE_CN_STOCK_KLINE_PATTERN['name']
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = " DELETE FROM `" + table_name + "` WHERE `date`= '%s' " % date
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_KLINE_PATTERN['columns'])

        dataKey = pd.DataFrame(results.keys())
        _columns = list(tbs.TABLE_CN_STOCK_FOREIGN_KEY['columns'].keys())
        dataKey.columns = _columns

        dataVal = pd.DataFrame(results.values())

        data = pd.merge(dataKey, dataVal, on=['code'], how='left')
        # 单例，时间段循环必须改时间
        date_str = date.strftime("%Y-%m-%d")
        if date.strftime("%Y-%m-%d") != data.iloc[0]['date']:
            data['date'] = date_str
        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")

    except Exception as e:
        logging.debug("{}处理异常：{}".format('klinepattern_data_daily_job.prepare', e))


def run_check(stocks, date=None, workers=40):
    data = {}
    columns = tbs.STOCK_KLINE_PATTERN_DATA['columns']
    data_column = columns
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_data = {executor.submit(kpr.get_pattern_recognition_tail, k, v, data_column, date=date): k for k, v in
                              stocks.items()}
            for future in concurrent.futures.as_completed(future_to_data):
                stock = future_to_data[future]
                try:
                    _data_ = future.result()
                    if _data_ is not None:
                        data[stock] = _data_
                except Exception as e:
                    logging.debug(
                        "{}处理异常：{}代码{}".format('klinepattern_data_daily_job.run_check', stock[1], e))
    except Exception as e:
        logging.debug("{}处理异常：{}".format('klinepattern_data_daily_job.run_check', e))
    if not data:
        return None
    else:
        return data


def main():
    # 使用方法传递。
    runt.run_with_args(prepare)


# main函数入口
if __name__ == '__main__':
    main()