use crate::Error;

pub(super) fn finish_backend_initialization<T>(
    backend: T,
    code: i32,
    error: impl FnOnce(i32) -> Error,
) -> Result<T, Error> {
    match code {
        prism_sys::PRISM_OK | prism_sys::PRISM_ERROR_ALREADY_INITIALIZED => Ok(backend),
        code => Err(error(code)),
    }
}

#[cfg(test)]
mod tests {
    use crate::Error;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;

    struct DropProbe(Arc<AtomicUsize>);

    impl Drop for DropProbe {
        fn drop(&mut self) {
            self.0.fetch_add(1, Ordering::SeqCst);
        }
    }

    fn native_error(code: i32) -> Error {
        Error::Native {
            code,
            message: "initialization failed".to_string(),
        }
    }

    #[test]
    fn successful_initialization_keeps_the_backend_handle() {
        let drops = Arc::new(AtomicUsize::new(0));
        let backend = super::finish_backend_initialization(
            DropProbe(Arc::clone(&drops)),
            prism_sys::PRISM_OK,
            native_error,
        )
        .expect("success is accepted");
        assert_eq!(drops.load(Ordering::SeqCst), 0);
        drop(backend);
        assert_eq!(drops.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn already_initialized_keeps_the_backend_handle() {
        let drops = Arc::new(AtomicUsize::new(0));
        let backend = super::finish_backend_initialization(
            DropProbe(Arc::clone(&drops)),
            prism_sys::PRISM_ERROR_ALREADY_INITIALIZED,
            native_error,
        )
        .expect("an existing initialization is accepted");
        assert_eq!(drops.load(Ordering::SeqCst), 0);
        drop(backend);
        assert_eq!(drops.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn failed_initialization_returns_the_error_and_releases_the_handle() {
        let drops = Arc::new(AtomicUsize::new(0));
        let result = super::finish_backend_initialization(
            DropProbe(Arc::clone(&drops)),
            prism_sys::PRISM_ERROR_NOT_INITIALIZED,
            native_error,
        );
        let error = match result {
            Ok(_) => panic!("a real initialization failure was accepted"),
            Err(error) => error,
        };
        assert_eq!(error.code(), Some(prism_sys::PRISM_ERROR_NOT_INITIALIZED));
        assert_eq!(drops.load(Ordering::SeqCst), 1);
    }
}
