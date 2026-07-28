import math
import os
from typing import Any

import httpx


SPECIALTY_RULES: list[tuple[tuple[str, ...], str, str]] = [
    (("glicemie", "hba1c", "glucoza", "diabet"), "Diabetologie", "valori legate de controlul glicemiei"),
    (("tsh", "tiroid", "vitamina d", "endocr"), "Endocrinologie", "valori hormonale sau metabolice"),
    (("ldl", "hdl", "colesterol", "triglicer", "tensiune"), "Cardiologie", "profil cardiovascular sau tensiune"),
    (("creatinin", "renal", "rinichi", "egfr"), "Nefrologie", "indicatori ai functiei renale"),
    (("hemoglobin", "hemat", "anemie"), "Hematologie", "valori ale hemoleucogramei"),
    (("respirat", "pulmon", "plamani"), "Pneumologie", "aspecte respiratorii"),
    (("digest", "hepatic", "ficat", "transamin"), "Gastroenterologie", "aspecte digestive sau hepatice"),
]


def places_enabled() -> bool:
    return bool(os.getenv("GOOGLE_PLACES_API_KEY", "").strip())


def recommend_specialties(analyses: list[dict[str, Any]], recommendations: list[dict[str, Any]]) -> list[dict[str, str]]:
    evidence = " ".join(
        [f"{item.get('name', '')} {item.get('notes', '')}" for item in analyses if item.get("status") != "normal"]
        + [f"{item.get('title', '')} {item.get('body', '')}" for item in recommendations if not item.get("completed")]
    ).lower()
    matches: list[dict[str, str]] = []
    for keywords, specialty, reason in SPECIALTY_RULES:
        if any(keyword in evidence for keyword in keywords):
            matches.append({"specialty": specialty, "reason": reason})
    if not matches:
        matches.append({"specialty": "Medicina interna", "reason": "evaluare generala a dosarului medical"})
    return matches[:3]


def _distance_km(latitude: float, longitude: float, place: dict[str, Any]) -> float | None:
    location = place.get("location") or {}
    if location.get("latitude") is None or location.get("longitude") is None:
        return None
    lat1, lon1, lat2, lon2 = map(
        math.radians,
        [latitude, longitude, float(location["latitude"]), float(location["longitude"])],
    )
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return round(6371 * 2 * math.asin(math.sqrt(value)), 1)


def _normalized_review(review: dict[str, Any]) -> dict[str, Any]:
    author = review.get("authorAttribution") or {}
    text = review.get("text") or {}
    return {
        "author": author.get("displayName", "Utilizator Google"),
        "author_uri": author.get("uri", ""),
        "rating": review.get("rating"),
        "text": text.get("text", ""),
        "relative_time": review.get("relativePublishTimeDescription", ""),
        "google_maps_uri": review.get("googleMapsUri", ""),
    }


def search_doctors(latitude: float, longitude: float, radius_km: float, specialties: list[str]) -> list[dict[str, Any]]:
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY nu este configurata.")

    field_mask = ",".join(
        [
            "places.id",
            "places.displayName",
            "places.formattedAddress",
            "places.location",
            "places.rating",
            "places.userRatingCount",
            "places.googleMapsUri",
            "places.websiteUri",
            "places.nationalPhoneNumber",
            "places.regularOpeningHours",
            "places.businessStatus",
            "places.reviews",
        ]
    )
    found: dict[str, dict[str, Any]] = {}
    with httpx.Client(timeout=15) as client:
        for specialty in specialties[:3]:
            response = client.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": field_mask,
                },
                json={
                    "textQuery": f"medic {specialty}",
                    "includedType": "doctor",
                    "strictTypeFiltering": False,
                    "languageCode": "ro",
                    "regionCode": "RO",
                    "pageSize": 8,
                    "locationBias": {
                        "circle": {
                            "center": {"latitude": latitude, "longitude": longitude},
                            "radius": radius_km * 1000,
                        }
                    },
                },
            )
            response.raise_for_status()
            for place in response.json().get("places", []):
                place_id = place.get("id")
                if not place_id:
                    continue
                if place_id not in found:
                    display_name = place.get("displayName") or {}
                    hours = place.get("regularOpeningHours") or {}
                    found[place_id] = {
                        "place_id": place_id,
                        "name": display_name.get("text", "Cabinet medical"),
                        "address": place.get("formattedAddress", ""),
                        "latitude": (place.get("location") or {}).get("latitude"),
                        "longitude": (place.get("location") or {}).get("longitude"),
                        "distance_km": _distance_km(latitude, longitude, place),
                        "rating": place.get("rating"),
                        "review_count": place.get("userRatingCount", 0),
                        "phone": place.get("nationalPhoneNumber", ""),
                        "website_uri": place.get("websiteUri", ""),
                        "google_maps_uri": place.get("googleMapsUri", ""),
                        "open_now": hours.get("openNow"),
                        "business_status": place.get("businessStatus", ""),
                        "reviews": [_normalized_review(review) for review in place.get("reviews", [])[:2]],
                        "matched_specialties": [specialty],
                    }
                elif specialty not in found[place_id]["matched_specialties"]:
                    found[place_id]["matched_specialties"].append(specialty)

    doctors = list(found.values())
    doctors.sort(
        key=lambda item: (
            -(float(item["rating"]) if item["rating"] is not None else 0),
            -int(item["review_count"] or 0),
            float(item["distance_km"]) if item["distance_km"] is not None else 10_000,
        )
    )
    return doctors[:15]
