// Bootstrap only the local/test replica set; never rewrite an existing configuration.
const port = process.env.MONGO_PORT || "27017";
const username = encodeURIComponent(process.env.MONGO_INITDB_ROOT_USERNAME);
const password = encodeURIComponent(process.env.MONGO_INITDB_ROOT_PASSWORD);
const connection = new Mongo(
    `mongodb://${username}:${password}@127.0.0.1:${port}/admin?authSource=admin&directConnection=true`,
);
const admin = connection.getDB("admin");

// The official image first starts a temporary standalone to create the root user.
const options = admin.runCommand({ getCmdLineOpts: 1 });
if (options.parsed?.replication?.replSet !== "rs0") {
    quit(1);
}

try {
    admin.runCommand({ replSetGetStatus: 1 });
} catch (error) {
    if (error.code !== 94) {
        throw error;
    }
    admin.runCommand({
        replSetInitiate: {
            _id: "rs0",
            members: [{ _id: 0, host: process.env.MONGO_REPLICA_HOST }],
        },
    });
}

quit(admin.runCommand({ hello: 1 }).isWritablePrimary ? 0 : 1);
