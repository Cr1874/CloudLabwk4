from sqlalchemy import Column, Integer, String
from database import Base

class Item(Base):
    __tablename__ = "items"

    #id is primary key. (unique identifier for each item)
    #name and description will store text data
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, unique=True) #index=True makes searching faster for these columns
    description = Column(String, index=True)