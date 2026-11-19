from flask import Blueprint, g, jsonify

from .. import services
from ..auth import login_required
from ..db import get_db

bp = Blueprint("tickets", __name__, url_prefix="/api/tickets")


@bp.get("/me")
@login_required
def my_tickets():
    return jsonify(tickets=services.list_user_tickets(get_db(), g.user["id"]))


@bp.get("/<code>")
@login_required
def get_ticket(code: str):
    return jsonify(ticket=services.get_ticket(get_db(), code.upper(), g.user))


@bp.post("/<code>/cancel")
@login_required
def cancel(code: str):
    return jsonify(ticket=services.cancel_ticket(get_db(), g.user["id"], code.upper()))
