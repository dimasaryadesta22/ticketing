from flask import Blueprint, g, jsonify, request

from .. import services
from ..auth import admin_required, login_required
from ..db import get_db

bp = Blueprint("events", __name__, url_prefix="/api/events")


@bp.get("")
def list_events():
    return jsonify(events=services.list_events(get_db()))


@bp.get("/<int:event_id>")
def get_event(event_id: int):
    return jsonify(event=services.serialize_event(services.get_event(get_db(), event_id)))


@bp.post("")
@admin_required
def create_event():
    event = services.create_event(get_db(), request.get_json(silent=True))
    return jsonify(event=event), 201


@bp.put("/<int:event_id>")
@admin_required
def update_event(event_id: int):
    event = services.update_event(get_db(), event_id, request.get_json(silent=True))
    return jsonify(event=event)


@bp.delete("/<int:event_id>")
@admin_required
def delete_event(event_id: int):
    force = request.args.get("force", "").lower() in ("1", "true", "yes")
    services.delete_event(get_db(), event_id, force=force)
    return "", 204


@bp.post("/<int:event_id>/tickets")
@login_required
def purchase(event_id: int):
    data = request.get_json(silent=True) or {}
    tickets = services.purchase_tickets(get_db(), g.user["id"], event_id, data.get("quantity", 1))
    return jsonify(tickets=tickets), 201
