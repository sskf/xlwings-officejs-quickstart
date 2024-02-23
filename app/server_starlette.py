from pathlib import Path

import custom_functions
import jinja2
import markupsafe
import xlwings as xw
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

this_dir = Path(__file__).resolve().parent


async def root(request):
    return JSONResponse({"status": "ok"})


async def hello(request):
    # Instantiate a Book object with the deserialized request body
    data = await request.json()
    with xw.Book(json=data) as book:
        # Use xlwings as usual
        sheet = book.sheets[0]
        cell = sheet["A1"]
        if cell.value == "Hello xlwings!":
            cell.value = "Bye xlwings!"
        else:
            cell.value = "Hello xlwings!"

        # Pass the following back as the response
        return JSONResponse(book.json())


async def capitalize_sheet_names_prompt(request):
    data = await request.json()
    with xw.Book(json=data) as book:
        book.app.alert(
            prompt="This will capitalize all sheet names!",
            title="Are you sure?",
            buttons="ok_cancel",
            # this is the JS function name that gets called when the user clicks a button
            callback="capitalizeSheetNames",
        )
        return JSONResponse(book.json())


async def capitalize_sheet_names(request):
    data = await request.json()
    with xw.Book(json=data) as book:
        for sheet in book.sheets:
            sheet.name = sheet.name.upper()
        return JSONResponse(book.json())


async def alert(request):
    """Boilerplate required by book.app.alert() and to show unhandled exceptions"""
    params = request.query_params
    return templates.TemplateResponse(
        "xlwings-alert.html",
        {
            "request": request,
            "prompt": markupsafe.escape(params["prompt"]).replace(
                "\n", markupsafe.Markup("<br>")
            ),
            "title": params["title"],
            "buttons": params["buttons"],
            "mode": params["mode"],
            "callback": params["callback"],
        },
    )


async def custom_functions_meta(request):
    return JSONResponse(xw.server.custom_functions_meta(custom_functions))


async def custom_functions_code(request):
    return Response(
        xw.server.custom_functions_code(custom_functions),
        media_type="application/javascript",
    )


async def custom_functions_call(request):
    data = await request.json()
    rv = await xw.server.custom_functions_call(data, custom_functions)
    return JSONResponse({"result": rv})


# Add xlwings.html as additional source for templates so the /xlwings/alert endpoint
# will find xlwings-alert.html. "mytemplates" can be a dummy if the app doesn't use
# own templates
loader = jinja2.ChoiceLoader(
    [
        jinja2.FileSystemLoader(this_dir / "mytemplates"),
        jinja2.PackageLoader("xlwings", "html"),
    ]
)
templates = Jinja2Templates(directory=this_dir / "mytemplates", loader=loader)


# Show XlwingsError in clear text instead of "Internal Server Error"
async def xlwings_exception_handler(request, exc):
    return PlainTextResponse(str(exc), status_code=500)


# Note that Starlette only handles CORS for specific exception,
# not for the root Exception
exception_handlers = {xw.XlwingsError: xlwings_exception_handler}

routes = [
    Route("/hello", hello, methods=["POST"]),
    Route(
        "/capitalize-sheet-names-prompt",
        capitalize_sheet_names_prompt,
        methods=["POST"],
    ),
    Route("/capitalize-sheet-names", capitalize_sheet_names, methods=["POST"]),
    Route("/xlwings/alert", alert),
    Route("/xlwings/custom-functions-meta", custom_functions_meta),
    Route("/xlwings/custom-functions-code", custom_functions_code),
    Route("/xlwings/custom-functions-call", custom_functions_call, methods=["POST"]),
    Route("/", root),
    # Serve static files (HTML and icons)
    # This could also be handled by an external web server such as nginx, etc.
    Mount("/", StaticFiles(directory=this_dir)),
]
# Never cache static files
StaticFiles.is_not_modified = lambda *args, **kwargs: False

# Office Scripts and custom functions in Excel on the web require CORS
middleware = [
    Middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["POST"], allow_headers=["*"]
    )
]

app = Starlette(
    debug=True,
    routes=routes,
    middleware=middleware,
    exception_handlers=exception_handlers,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server_starlette:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        ssl_keyfile=this_dir.parent / "certs" / "localhost+2-key.pem",
        ssl_certfile=this_dir.parent / "certs" / "localhost+2.pem",
    )
