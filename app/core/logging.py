import logging
from rich.logging import RichHandler

def configure_logger():
    handler = RichHandler(
        show_time=False,
        show_level=True,     
        show_path=False,
        rich_tracebacks=True,
        markup=True,
    )
    fmt = "-->  %(asctime)s | %(name)s | %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[handler]
    )
    
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)