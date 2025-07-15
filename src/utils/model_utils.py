"""
模型相关工具函数
Model-related utility functions
"""
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import class_mapper

def orm_to_dict(obj: object) -> dict:
    """
    将一个SQLAlchemy ORM对象（瞬时态或持久态）及其关联对象递归地转换为字典。
    这是一个更健壮的版本，可以安全地处理None值和关联关系。
    """
    if obj is None:
        return None

    data = {}
    # 遍历所有已定义的列属性
    for column in class_mapper(obj.__class__).columns:
        value = getattr(obj, column.name)
        if isinstance(value, (datetime, date)):
            data[column.name] = value.isoformat()
        elif isinstance(value, Decimal):
            data[column.name] = float(value)
        else:
            data[column.name] = value

    # 遍历所有已定义的关联关系
    for relationship in class_mapper(obj.__class__).relationships:
        # 检查关联属性是否存在于对象实例中
        if hasattr(obj, relationship.key):
            related_obj = getattr(obj, relationship.key)
            if related_obj is None:
                # 如果关联对象是None，根据关系类型（列表或单个对象）设置为空列表或None
                data[relationship.key] = [] if relationship.uselist else None
            else:
                if relationship.uselist:
                    # 如果是列表关系，递归转换列表中的每个对象
                    data[relationship.key] = [orm_to_dict(o) for o in related_obj]
                else:
                    # 如果是单个对象关系，直接递归转换
                    data[relationship.key] = orm_to_dict(related_obj)
    
    return data
