## MongoDB sharded cluster with FastAPI
This project involves setting up a MongoDB sharded cluster and a FastAPI application for data processing. The setup ensures proper replication and sharding of the database. Docker Compose is used to manage the application and its services.

### Introduction to Project Files
- **docker-compose.yml**: this file configures the MongoDB sharded cluster and FastAPI application services.
- **main.py**: this file implements the FastAPI application to handle CSV uploads, data processing, and histogram generation.
- **requirements.txt**: this file lists the dependencies required for the FastAPI application.
- **Dockerfile**: this file sets up the FastAPI application environment using a Python 3.10 base image.


## Running application

### Checking and terminating unwanted processes
To check if any application runs on port 27017, use: `netstat -ano | findstr :27017`. To terminate a process, use: `taskkill /PID NAME /F`. Replace `NAME` with the actual process ID.
​
### Setting up the application
Navigate to the directory containing the **docker-compose.yml** file and run:
- `docker-compose build` 
- `docker-compose up`

    
To initialize the config server and  shard server  replica set run:  
- `docker exec -it mongocfg1 mongosh --eval "rs.initiate({_id: 'mongors1conf', configsvr: true, members: [{ _id: 0, host: 'mongocfg1:27017' }, { _id: 1, host: 'mongocfg2:27017' }, { _id: 2, host: 'mongocfg3:27017' }]})"`
- `docker exec -it mongors1n1 mongosh --eval "rs.initiate({_id: 'mongors1', members: [{ _id: 0, host: 'mongors1n1:27017' }, { _id: 1, host: 'mongors1n2:27017' }, { _id: 2, host: 'mongors1n3:27017' }]})"`

### Add shards to the cluster
To add the shards to the cluster run: 
- `docker exec -it mongos1 mongosh --eval "sh.addShard('mongors1/mongors1n1:27017,mongors1n2:27017,mongors1n3:27017')"`

### Enable sharding on the database
To enable sharding for the database run:
- `docker exec -it mongos1 mongosh --eval "sh.enableSharding('db_database')"`

### Create an appropriate index on the collections
Create an index on the *MMSI* variable for the 'vessels' and 'filtered_vessels' collections: 
- `docker exec -it mongos1 mongosh --eval "db.getSiblingDB('db_database').vessels.createIndex({'MMSI': 1})"`
- `docker exec -it mongos1 mongosh --eval "db.getSiblingDB('db_database').filtered_vessels.createIndex({'MMSI': 1})"`

### Shard the collections
Shard the 'vessels' and 'filtered_vessels'  collections: 
- `docker exec -it mongos1 mongosh --eval "sh.shardCollection('db_database.vessels', {'MMSI': 1})"`
- `docker exec -it mongos1 mongosh --eval "sh.shardCollection('db_database.filtered_vessels', {'MMSI': 1})"`

## Data insertion in parallel

### Read data from a CSV file
The program reads data from an uploaded CSV file and processes it in chunks. In this case, it was chosen to insert the first one hundred thousand lines of vessel data.
### Use separate instances of MongoClient for inserting data
Each parallel thread  utilizes a separate instance of MongoClient to concurrently insert data into the database. The data is divided into chunks, and each chunk is inserted into the MongoDB 'vessels' collection using multiple threads.

### Accessing Data
- Inserted data can be accessed in the 'vessels' collection within the 'db_database' database. In this case, MongoDB Compass was used. The database was accessed at `mongodb://root:defaultpassword@mongodb:27017`
- The FastAPI application is accessible at http://localhost:8800. Users can select a dataset for insertion.
    
    
## Data noise filtering in parallel
After noise removal, 65247 observations were left.

### Parallel data noise filtering

The program filters out noise from the inserted data based on specific criteria:

- Vessels with less than 100 data points are removed.
- Rows with missing or invalid fields (*Navigational status*, *MMSI, Latitude*, *Longitude*, *ROT*, *SOG*, *COG*, *Heading*) are excluded.

The filtered data is stored in a separate 'filtered_vessels' collection in MongoDB.

### Creating Indexes

Appropriate indexes are created on the *MMSI* and *# Timestamp* columns to improve the efficiency of filtering and querying.
    
## Calculation of Δt and generation of histograms


Time differences (Δt) in milliseconds between subsequent data points for each filtered vessel from the 'filtered_vessels' collection are calculated and visualized in histograms. These histograms are saved as images in the **histograms** directory.


### Histograms for Data Analysis

![Histogram 1](https://github.com/MatasSepikas/BigDataAssignment3/blob/main/histograms/histogram1.png)
Histogram of Δt (time differences in milliseconds)

Histogram shows numerous data points with Δt values from 0 to 50,000. A long tail extends to higher Δt values, indicating occasional larger gaps between data points.

![Histogram 2](histograms\histogram2.png)
Histogram of Δt (time differences in milliseconds)

This histogram emphasizes Δt values up to 50,000 milliseconds, showing a prominent peak at around 10,000 milliseconds. The distribution indicates that data points are mostly collected approximately every 15 seconds, with some variation.

### Presentation of the solution


To demonstrate the resilience of the MongoDB sharded cluster, follow these steps:

Check the Status of the Entire Replica Set Using mongos Before Stopping a Member:
- `docker exec -it mongors1n1 mongosh --eval "rs.status()"`
Stop the mongors1n3 Member of the Replica Set:
- `docker stop mongors1n1`
Check the Status of the Entire Replica Set Using mongos After Stopping a Member:
- `docker exec -it mongors1n2 mongosh --eval "rs.status()"`

When the primary member `mongors1n1` stops, the replica set will automatically reconfigure itself to maintain availability. The status checks will indicate that `mongors1n1` is unreachable, but the other members (`mongors1n2`, which became primary, and `mongors1n3`) will continue to function, ensuring that the database remains operational. [This example is demonstrated in a recording.](https://vult-my.sharepoint.com/:v:/r/personal/matas_sepikas_mif_stud_vu_lt/Documents/Mongo_database_instance_failures.mp4?csf=1&web=1&e=52gcOx&nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJTdHJlYW1XZWJBcHAiLCJyZWZlcnJhbFZpZXciOiJTaGFyZURpYWxvZy1MaW5rIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXcifX0%3D)
