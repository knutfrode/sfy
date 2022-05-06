use eyre::Result;
use sqlx::SqlitePool;
use std::path::{Path, PathBuf};

#[derive(Debug)]
pub struct Database {
    db: SqlitePool,
}

impl Database {
    pub async fn open(path: impl AsRef<Path>) -> Result<Database> {
        let path: PathBuf = path.as_ref().into();
        info!("opening database at: {:?}", path);

        let db = SqlitePool::connect(&format!("sqlite:{}", path.to_string_lossy())).await?;

        info!("running db migrations..");
        sqlx::migrate!("./migrations").run(&db).await?;

        Ok(Database { db })
    }

    /// Open buoy for writing.
    pub async fn buoy(&self, dev: &str) -> eyre::Result<Buoy> {
        let buoy = sqlx::query!("SELECT dev, name FROM buoys where dev = ?1", dev)
            .fetch_optional(&self.db)
            .await?;

        if buoy.is_none() {
            info!("New buoy registered: {}", dev);
            sqlx::query!("INSERT INTO buoys (dev) VALUES ( ?1 )", dev)
                .execute(&self.db)
                .await?;
        }

        let name = buoy.map(|b| b.name).flatten();

        Ok(Buoy {
            dev: String::from(dev),
            name,
            db: self.db.clone().clone(),
        })
    }

    /// Get list of buoys.
    pub async fn buoys(&self) -> eyre::Result<Vec<(String, String)>> {
        let buoys = sqlx::query!("SELECT dev, name FROM buoys ORDER BY dev")
            .fetch_all(&self.db)
            .await?
            .iter()
            .map(|r| {
                (
                    r.dev.clone().unwrap_or(String::new()),
                    r.name.clone().unwrap_or(String::new()),
                )
            })
            .collect();

        Ok(buoys)
    }

    #[cfg(test)]
    pub async fn temporary() -> Database {
        warn!("create temporary database at in memory");

        Database::open(":memory:").await.unwrap()
    }
}

#[derive(Debug)]
pub struct Buoy {
    dev: String,
    name: Option<String>,
    db: SqlitePool,
}

impl Buoy {
    /// Append new event to buoy, `name` is parsed serial number of buoy.
    pub async fn append(
        &mut self,
        name: Option<String>,
        event: impl AsRef<Path>,
        received: u64,
        data: impl AsRef<[u8]>,
    ) -> eyre::Result<()> {
        let data = data.as_ref();
        let event = event.as_ref().to_string_lossy().into_owned();

        if let Some(name) = name {
            if self.name.as_ref() != Some(&name) {
                info!("updating name of buoy from {:?} to {:?}", self.name, name);
                sqlx::query!(
                    "INSERT OR REPLACE INTO buoys (dev, name) VALUES ( ?1, ?2 )",
                    self.dev,
                    name
                )
                .execute(&self.db)
                .await?;
            }
        }

        debug!(
            "buoy: {} ({:?}): appending event: {:?}, size: {}",
            self.dev,
            self.name,
            event,
            data.len()
        );

        let r = received as i64;
        sqlx::query!(
            "INSERT INTO events (dev, received, event, data) VALUES ( ?1, ?2, ?3, ?4 )",
            self.dev,
            r,
            event,
            data
        )
        .execute(&self.db)
        .await?;

        Ok(())
    }

    pub async fn entries(&self) -> Result<Vec<String>> {
        let events = sqlx::query!(
            "SELECT received, event FROM events where dev = ?1 ORDER BY event",
            self.dev
        )
        .fetch_all(&self.db)
        .await?
        .iter()
        .map(|r| {
            format!(
                "{}-{}",
                r.received.clone(),
                r.event.clone().unwrap_or(String::new())
            )
        })
        .collect();

        Ok(events)
    }

    /// Get the last received axl.qo entry for the buoy.
    pub async fn last(&self) -> Result<Vec<u8>> {
        let event = sqlx::query!("SELECT data FROM events WHERE dev = ?1 AND instr(event, 'axl.qo') ORDER BY event DESC LIMIT 1", self.dev)
            .fetch_one(&self.db)
            .await?;

        match event.data {
            Some(event) => Ok(event),
            None => Err(eyre!("No axl entry found.")),
        }
    }

    pub async fn get(&self, file: impl AsRef<Path>) -> Result<Vec<u8>> {
        let file = file.as_ref().to_string_lossy().into_owned();

        let (received, file) = file
            .split_once('-')
            .ok_or(eyre!("incorrect format of event"))?;

        let event = sqlx::query!(
            "SELECT data FROM events WHERE dev = ?1 AND received = ?2 AND event = ?3",
            self.dev,
            received,
            file
        )
        .fetch_one(&self.db)
        .await?;

        match event.data {
            Some(event) => Ok(event),
            None => Err(eyre!("No such event found.")),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn create_temporary() {
        let _db = Database::temporary().await;
    }

    #[tokio::test]
    async fn get_new_buoy() {
        let db = Database::temporary().await;
        let _b = db.buoy("test-01").await;
    }

    #[tokio::test]
    async fn add_some_entries() {
        let db = Database::temporary().await;
        let mut b = db.buoy("buoy-01").await.unwrap();

        b.append(None, "entry-0", 0, "data-0").await.unwrap();
        b.append(None, "entry-1", 0, "data-1").await.unwrap();

        assert_eq!(b.get("0-entry-0").await.unwrap(), b"data-0");
    }

    #[tokio::test]
    async fn add_existing_entry() {
        let db = Database::temporary().await;
        let mut b = db.buoy("buoy-01").await.unwrap();

        b.append(None, "entry-0", 0, "data-0").await.unwrap();
        assert!(b.append(None, "entry-0", 0, "data-1").await.is_err());
    }

    #[tokio::test]
    async fn list_buoys() {
        let db = Database::temporary().await;
        db.buoy("buoy-01").await.unwrap();
        db.buoy("buoy-02").await.unwrap();

        let devs = db.buoys().await.unwrap();
        let devs: Vec<_> = devs.iter().map(|(dev, _)| dev).collect();

        assert_eq!(devs, ["buoy-01", "buoy-02"]);
    }

    #[tokio::test]
    async fn list_entries() {
        let db = Database::temporary().await;
        let mut b = db.buoy("buoy-01").await.unwrap();
        b.append(None, "entry-0", 0, "data-0").await.unwrap();
        b.append(None, "entry-1", 0, "data-1").await.unwrap();

        assert_eq!(
            db.buoy("buoy-01").await.unwrap().entries().await.unwrap(),
            ["0-entry-0", "0-entry-1"]
        );
    }

    #[tokio::test]
    async fn append_get() {
        let db = Database::temporary().await;
        let mut b = db.buoy("buoy-01").await.unwrap();
        b.append(None, "entry-0", 0, "data-0").await.unwrap();

        assert_eq!(b.get("0-entry-0").await.unwrap(), b"data-0");
    }

    #[tokio::test]
    async fn append_last() {
        let db = Database::temporary().await;
        let mut b = db.buoy("buoy-01").await.unwrap();
        b.append(None, "entry-0-axl.qo", 0, "data-0").await.unwrap();
        b.append(None, "entry-1-sessi.qo", 0, "data-1").await.unwrap();

        assert_eq!(b.last().await.unwrap(), b"data-0");
    }
}
