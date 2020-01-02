# 众筹数据

## `transferData.py`
> 将众筹项目数据转换为pd.DataFrame()对象
- `ProjData`类用于转换众筹项目动态数据、主页呈现时间数据和评论历史数据
- `IterProj`类用于构建某个`_id`集合对应的迭代器，以减小内存占用

## `crawFounders.py`
> 获取所有项目发起人的信息
- `crawFounders`类用于获取项目发起人的信息

## `Data-analysis-Bass.ipynb`
> 利用`Bass`模型拟合扩散数据
