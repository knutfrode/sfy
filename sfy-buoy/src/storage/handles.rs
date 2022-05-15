use embedded_sdmmc::{
    BlockDevice, Controller, Directory, Error as GenericSdMmcError, File, Mode, TimeSource, Volume,
};

pub struct DirHandle<'c, 'v, D: BlockDevice, T: TimeSource> {
    ctrl: &'c mut Controller<D, T>,
    vol: &'v mut Volume,
    dir: Option<Directory>,
}

impl<'c, 'v, D: BlockDevice, T: TimeSource> DirHandle<'c, 'v, D, T> {
    pub fn from(
        ctrl: &'c mut Controller<D, T>,
        vol: &'v mut Volume,
        dir: Directory,
    ) -> DirHandle<'c, 'v, D, T> {
        DirHandle {
            ctrl,
            vol,
            dir: Some(dir),
        }
    }

    pub fn open_root(
        ctrl: &'c mut Controller<D, T>,
        vol: &'v mut Volume,
    ) -> Result<DirHandle<'c, 'v, D, T>, GenericSdMmcError<D::Error>> {
        let dir = ctrl.open_root_dir(vol)?;
        Ok(Self::from(ctrl, vol, dir))
    }

    pub fn open_file(
        &mut self,
        name: &str,
        mode: Mode,
    ) -> Result<FileHandle<'_, '_, D, T>, GenericSdMmcError<D::Error>> {
        let dir = self.dir.as_ref().unwrap();
        let file = self.ctrl.open_file_in_dir(self.vol, dir, name, mode)?;
        Ok(FileHandle::from(self.ctrl, self.vol, file))
    }
}

impl<D: BlockDevice, T: TimeSource> Drop for DirHandle<'_, '_, D, T> {
    fn drop(&mut self) {
        let dir = self.dir.take();

        if let Some(dir) = dir {
            self.ctrl.close_dir(&self.vol, dir);
        }
    }
}

/// A FileHandle that requires exclusive access to the Controller and Volume. Not a big loss
/// for us, but it allows use to make _more_ sure the file-handle is closed, and not
/// accidently left open because of early-returns `(?)`.
pub struct FileHandle<'c, 'v, D: BlockDevice, T: TimeSource> {
    ctrl: &'c mut Controller<D, T>,
    vol: &'v mut Volume,
    file: Option<File>,
}

impl<'c, 'v, D: BlockDevice, T: TimeSource> FileHandle<'c, 'v, D, T> {
    pub fn from(ctrl: &'c mut Controller<D, T>, vol: &'v mut Volume, file: File) -> Self {
        FileHandle {
            ctrl,
            vol,
            file: Some(file),
        }
    }

    pub fn read(&mut self, buf: &mut [u8]) -> Result<usize, GenericSdMmcError<D::Error>> {
        let file = self.file.as_mut().unwrap();
        self.ctrl.read(&self.vol, file, buf)
    }

    pub fn write(&mut self, buf: &[u8]) -> Result<usize, GenericSdMmcError<D::Error>> {
        let file = self.file.as_mut().unwrap();
        self.ctrl.write(&mut self.vol, file, buf)
    }
}

impl<D: BlockDevice, T: TimeSource> Drop for FileHandle<'_, '_, D, T> {
    fn drop(&mut self) {
        let file = self.file.take();

        if let Some(file) = file {
            self.ctrl.close_file(&self.vol, file).ok();
        }
    }
}
