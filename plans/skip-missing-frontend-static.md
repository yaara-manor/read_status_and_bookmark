# Skip missing frontend static dir

`FRONTEND_DIR` is Vite **build output**, not `./frontend` source.
`mount_frontend` only if `FRONTEND_DIR.is_dir()`.
