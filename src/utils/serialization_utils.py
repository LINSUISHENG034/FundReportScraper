"""
序列化工具
Serialization Utilities
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict
from sqlalchemy.orm import class_mapper


def sqlalchemy_to_dict(obj: Any) -> Dict[str, Any]:
    """
    将一个SQLAlchemy ORM对象递归地转换为一个可序列化为JSON的字典。
    Converts a SQLAlchemy ORM object into a JSON-serializable dictionary recursively.
    """
    if obj is None:
        return None

    data = {}
    # 遍历所有列
    for column in class_mapper(obj.__class__).columns:
        value = getattr(obj, column.name)
        # 处理特殊数据类型
        if isinstance(value, (datetime, date)):
            data[column.name] = value.isoformat()
        elif isinstance(value, Decimal):
            data[column.name] = float(value)
        else:
            data[column.name] = value

    # 递归处理关联对象
    for relationship in class_mapper(obj.__class__).relationships:
        # 检查关联属性是否存在，避免在未加载时触发查询
        if relationship.key in obj.__dict__:
            related_obj = getattr(obj, relationship.key)
            if related_obj is not None:
                if relationship.uselist:
                    data[relationship.key] = [
                        sqlalchemy_to_dict(o) for o in related_obj
                    ]
                else:
                    data[relationship.key] = sqlalchemy_to_dict(related_obj)

    return data
