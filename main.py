from codecs import iterdecode
import csv

from fastapi import FastAPI, Depends, File, HTTPException, UploadFile
from fastapi.params import File
from sqlalchemy.orm import Session
import models, schemas
from database import SessionLocal, engine
from fastapi.middleware.cors import CORSMiddleware
import logging
logging.basicConfig(filename='server.log', encoding='utf-8', level=logging.DEBUG)
# Create all tables in the database
models.Base.metadata.create_all(bind=engine)

# Create the FastAPI application
app = FastAPI()

# Add CORS middleware to allow React frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React's default port
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# CREATE - Add a new item
@app.post("/items/", response_model=schemas.Item)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    db_item = models.Item(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    logging.info("CREATE : %s ", item)
    return db_item

# READ - Get all items
@app.get("/items/", response_model=list[schemas.Item])
def read_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = db.query(models.Item).offset(skip).limit(limit).all()
    return items

# READ - Get a single item by ID
@app.get("/items/{item_id}", response_model=schemas.Item)
def read_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

# UPDATE - Update an existing item
@app.put("/items/{item_id}", response_model=schemas.Item)
def update_item(item_id: int, item: schemas.ItemCreate, db: Session = Depends(get_db)):
    db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    for field, value in item.dict().items():
        setattr(db_item, field, value)

    db.commit()
    db.refresh(db_item)
    return db_item

# DELETE - Remove an item
@app.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(item)
    db.commit()
    return {"message": "Item deleted successfully"}


@app.post("/items-upload/csv/")
async def upload_items_csv(csvFile: UploadFile = File(...), db: Session = Depends(get_db)):
    if not csvFile.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a .csv file.")

    try:
        text_stream = iterdecode(csvFile.file, 'utf-8')
        reader = csv.reader(text_stream, delimiter=",", quotechar='"')
        
        headers = next(reader, None) 
        if not headers:
            raise HTTPException(status_code=400, detail="The CSV file is empty.")

        # Clean headers to match your model properties exactly
        headers = [h.strip().lower() for h in headers]
        new_items = []
        
        for row_index, row in enumerate(reader, start=2):
            if not row or len(row) != len(headers):
                continue 

            row_dict = dict(zip(headers, row))
            
            try:
                # If your fields (like price or stock) need to be numbers,
                # you can convert them here before passing to models.Item
                db_item = models.Item(**row_dict)
                new_items.append(db_item)
            except Exception as mapping_error:
                logging.error(f"Row {row_index} mapping failed: {str(mapping_error)}")
                raise HTTPException(
                    status_code=422, 
                    detail=f"Row {row_index} layout is invalid. Match your columns with item attributes."
                )

        if new_items:
            db.add_all(new_items)
            db.commit()
            logging.info(f"BULK CREATE: Successfully uploaded {len(new_items)} items from CSV.")
            return {
                "message": "CSV data successfully imported!",
                "items_imported": len(new_items)
            }
        
        return {"message": "No valid data rows found to import.", "items_imported": 0}

    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"CSV Batch upload crashed: {str(e)}")
        db.rollback() 
        raise HTTPException(status_code=500, detail=f"Server failed to process file: {str(e)}")


