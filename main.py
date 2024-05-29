from fastapi import FastAPI, UploadFile, File, HTTPException
import pandas as pd
from pymongo import MongoClient
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import os
import matplotlib.pyplot as plt


app = FastAPI(title="My FastAPI")


def get_new_mongo_client():
    user = "root"
    password = "defaultpassword"
    client = MongoClient(f"mongodb://{user}:{password}@mongodb:27017")
    return client


def insert_data(chunk):
    client = get_new_mongo_client()
    db = client.db_database
    collection = db.vessels
    try:
        collection.insert_many(chunk, ordered=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


def process_chunk(chunk):
    chunk = chunk.dropna(subset=['Navigational status', 'MMSI', 'Latitude',
                                 'Longitude', 'ROT', 'SOG', 'COG', 'Heading'])
    chunk = chunk.groupby('MMSI').filter(lambda x: len(x) >= 10)
    return chunk


@app.post("/upload_csv/")
async def upload_csv(file: UploadFile = File(...), limit: int = 1000, num_threads: int = 4):
    file_path = f"/tmp/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(file.file.read())

    data = pd.read_csv(file_path, nrows=limit)
    data_dict = data.to_dict('records')
    chunk_size = len(data_dict) // num_threads + (len(data_dict) % num_threads > 0)
    chunks = [data_dict[i:i + chunk_size] for i in range(0, len(data_dict), chunk_size)]

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(insert_data, chunk) for chunk in chunks]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error occurred: {e}")

    return {"Status": "Working", "Message": f"Data inserted into MongoDB", "file_path": file_path}


@app.post("/process_dataset/")
async def process_dataset(num_parallel_tasks: int = 4):

    client = get_new_mongo_client()
    db = client.db_database
    collection = db.vessels
    data = pd.DataFrame(list(collection.find()))
    data['# Timestamp'] = pd.to_datetime(data['# Timestamp'])
    data.sort_values(['MMSI', '# Timestamp'], inplace=True)
    vessel_groups = data.groupby('MMSI')
    vessel_chunks = [group for _, group in vessel_groups]
    filtered_data_chunks = []

    with ProcessPoolExecutor(max_workers=num_parallel_tasks) as executor:
        result_chunks = list(executor.map(process_chunk, vessel_chunks))
        filtered_data_chunks.extend(result_chunks)

    filtered_data = pd.concat(filtered_data_chunks)

    if filtered_data.empty:
        raise HTTPException(status_code=400, detail="No data to process after filtering")

    filtered_collection = db.filtered_vessels
    try:
        filtered_collection.insert_many(filtered_data.to_dict('records'), ordered=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

    filtered_collection.create_index([('MMSI', 1)])
    filtered_collection.create_index([('# Timestamp', 1)])

    return {
        "Status": "Working",
        "Message": "Dataset processed and filtered data stored"
    }

@app.post("/delta_t/")
async def delta_t():

    client = get_new_mongo_client()
    db = client.db_database
    filtered_collection = db.filtered_vessels
    data = pd.DataFrame(list(filtered_collection.find()))
    data['# Timestamp'] = pd.to_datetime(data['# Timestamp'])
    data.sort_values(['MMSI', '# Timestamp'], inplace=True)
    data['Delta_t'] = data.groupby('MMSI')['# Timestamp'].diff().dt.total_seconds() * 1000
    data = data.dropna(subset=['Delta_t'])
    script_dir = os.path.dirname(__file__)
    data_dir = os.path.join(script_dir, "histograms")
    os.makedirs(data_dir, exist_ok=True)

    plt.figure(figsize=(10, 6))
    plt.hist(data['Delta_t'], bins=100, edgecolor='k', alpha=0.7)
    plt.title(r'Histogram of $\Delta t$ (time differences in milliseconds)')
    plt.xlabel(r'$\Delta t$ (ms)')
    plt.ylabel('Frequency')
    plt.grid(True)
    plt.xticks(range(0, int(data['Delta_t'].max()) + 50000, 50000), rotation=45)
    hist1_path = os.path.join(data_dir, "histogram1.png")
    plt.savefig(hist1_path)
    plt.close()

    plt.figure(figsize=(10, 6))
    plt.hist(data['Delta_t'], bins=50, range=(0, 50000), edgecolor='k')
    plt.title(r'Histogram of $\Delta t$ (time differences in milliseconds)')
    plt.xlabel(r'$\Delta t$ (ms)')
    plt.ylabel('Frequency')
    plt.grid(True)
    plt.xticks(range(0,50000, 5000), rotation=45)
    hist2_path = os.path.join(data_dir, "histogram2.png")
    plt.savefig(hist2_path)
    plt.close()

    return {
        "Status": "Working",
        "message": "Delta t calculated and histograms generated",
        "histogram1": hist1_path,
        "histogram2": hist2_path
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8800)
