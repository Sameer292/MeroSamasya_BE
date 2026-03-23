from fastapi import FastAPI

app = FastAPI(
    title="MeroSamasya",
    description="MeroSamasya backend API",
    version="0.0.1",
    swagger_ui_parameters={"persistAuthorization": True},
    contact={
        "name": "MeroSamasya",
        "url": "https://github.com/sameer292/merosamasya_be",
    }
)

@app.get("/",tags=["Root"])
def root():
    return {"message": "Working"}
