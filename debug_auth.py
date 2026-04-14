#!/usr/bin/env python3
"""Скрипт для отладки авторизации Atmeex Airnanny API."""

import requests
import json
import sys

BASE_URL = "https://api.iot.atmeex.com"


def pretty(response):
    """Красивый вывод ответа."""
    print(f"Status: {response.status_code}")
    ct = response.headers.get("Content-Type", "")
    if "json" in ct:
        try:
            body = response.json()
            print(f"Body:\n{json.dumps(body, indent=2, ensure_ascii=False)}")
        except Exception:
            print(f"Body (text): {response.text[:2000]}")
    else:
        print(f"Content-Type: {ct}")
        print(f"Body (text): {response.text[:2000]}")


def send_sms(phone):
    """Отправка SMS-кода."""
    headers = {"Content-Type": "application/json"}
    data = {"grant_type": "phone_code", "phone": phone}
    resp = requests.post(f"{BASE_URL}/auth/signup", json=data, headers=headers, timeout=10)
    print(f"SMS -> {resp.status_code}")
    if resp.status_code == 200:
        print("✅ SMS отправлено!")
        return True
    else:
        print(f"❌ Ошибка: {resp.text[:500]}")
        return False


def login_phone(phone, code):
    """Вход по телефону и коду."""
    headers = {"Content-Type": "application/json"}
    data = {"grant_type": "phone_code", "phone": phone, "phone_code": code}
    resp = requests.post(f"{BASE_URL}/auth/signin", json=data, headers=headers, timeout=10)
    if resp.status_code == 200:
        body = resp.json()
        print(f"✅ Авторизация успешна!")
        return body.get("access_token")
    else:
        print(f"❌ Ошибка: {resp.status_code} {resp.text[:300]}")
        return None


def explore_api(token):
    """Исследование всех эндпоинтов API."""
    headers = {"Content-Type": "application/json", "Authorization": token}

    print("\n" + "=" * 60)
    print("ИССЛЕДОВАНИЕ API")
    print("=" * 60)

    # Список путей для проверки
    paths = [
        # Addresses
        "/addresses", "/address",
        # Rooms
        "/rooms", "/room",
        # Devices
        "/devices",
        # User
        "/user", "/user/addresses", "/user/rooms", "/user/devices", "/user/profile",
        # Houses/Locations
        "/houses", "/locations", "/places", "/buildings", "/facilities", "/sites",
        # Other
        "/notifications", "/settings", "/profile", "/account",
        "/dashboard", "/statuses", "/groups", "/zones",
        # Device-related
        "/device", "/devices/list", "/devices/all",
        # Auth user info
        "/auth/user", "/auth/me", "/auth/profile",
    ]

    print("\n--- GET запросы ---")
    for path in paths:
        url = f"{BASE_URL}{path}"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            ct = resp.headers.get("Content-Type", "")
            if resp.status_code == 500 and "json" not in ct:
                print(f"  ... GET {path} -> 500 (HTML)")
                continue

            print(f"\n  >>> GET {path} -> {resp.status_code}")
            if "json" in ct:
                try:
                    body = resp.json()
                    text = json.dumps(body, indent=2, ensure_ascii=False)
                    # Ограничиваем вывод
                    if len(text) > 3000:
                        print(f"  {text[:3000]}...")
                        print(f"  [... обрезано, всего {len(text)} символов]")
                    else:
                        print(f"  {text}")
                except Exception:
                    print(f"  Body: {resp.text[:500]}")
            else:
                print(f"  Body (text): {resp.text[:200]}")
        except Exception as e:
            print(f"  ... GET {path} -> ERROR: {e}")

    # POST варианты для создания/получения
    print("\n\n--- POST запросы (пробы) ---")
    post_paths = [
        ("/addresses", {}),
        ("/rooms", {}),
        ("/devices", {}),
        ("/user/addresses", {}),
        ("/user/rooms", {}),
    ]
    for path, data in post_paths:
        url = f"{BASE_URL}{path}"
        try:
            resp = requests.post(url, json=data, headers=headers, timeout=10)
            ct = resp.headers.get("Content-Type", "")
            if resp.status_code == 500 and "json" not in ct:
                continue
            print(f"\n  >>> POST {path} -> {resp.status_code}")
            if "json" in ct:
                print(f"  {resp.text[:1000]}")
        except Exception as e:
            print(f"  ... POST {path} -> ERROR: {e}")

    # GET /devices с разными параметрами
    print("\n\n--- /devices с параметрами ---")
    for params in [
        {},
        {"with_condition": 1},
        {"with_settings": 1},
        {"with_condition": 1, "with_settings": 1},
        {"with_condition": "true"},
        {"with_condition": "1"},
        {"include": "condition,settings"},
        {"expand": "condition,settings"},
    ]:
        try:
            resp = requests.get(f"{BASE_URL}/devices", params=params, headers=headers, timeout=10)
            print(f"\n  GET /devices params={params} -> {resp.status_code}")
            if resp.status_code == 200:
                ct = resp.headers.get("Content-Type", "")
                if "json" in ct:
                    body = resp.json()
                    text = json.dumps(body, indent=2, ensure_ascii=False)
                    print(f"  {text[:2000]}")
                else:
                    print(f"  Content-Type: {ct}")
            else:
                print(f"  Body: {resp.text[:300]}")
        except Exception as e:
            print(f"  ERROR: {e}")

    # Если нашли addresses — углубляемся
    print("\n\n--- Проверка вложенных путей ---")
    nested_paths = [
        "/addresses/1",
        "/addresses/1/rooms",
        "/rooms/1",
        "/rooms/1/devices",
        "/rooms/1/device",
    ]
    for path in nested_paths:
        url = f"{BASE_URL}{path}"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            ct = resp.headers.get("Content-Type", "")
            if resp.status_code == 500 and "json" not in ct:
                print(f"  ... GET {path} -> 500")
                continue
            print(f"\n  >>> GET {path} -> {resp.status_code}")
            if "json" in ct:
                print(f"  {resp.text[:1000]}")
        except Exception as e:
            print(f"  ... GET {path} -> ERROR: {e}")


def main():
    print("Atmeex Airnanny API — Отладка")
    print("=" * 60)

    if len(sys.argv) < 2:
        print("""
Использование:
  python debug_auth.py sms <phone>                    — Отправить SMS
  python debug_auth.py login <phone> <code>           — Вход по коду
  python debug_auth.py explore <token>                — Исследовать API
  python debug_auth.py all <phone> <code>             — SMS + вход + исследование

Примеры:
  python debug_auth.py sms "+7(903)967-38-00"
  python debug_auth.py login "+7(903)967-38-00" 1234
  python debug_auth.py explore "eyJ0eXAi..."
  python debug_auth.py all "+7(903)967-38-00" 1234
""")
        sys.exit(1)

    command = sys.argv[1]

    if command == "sms":
        phone = sys.argv[2]
        send_sms(phone)

    elif command == "login":
        phone = sys.argv[2]
        code = sys.argv[3]
        token = login_phone(phone, code)
        if token:
            print(f"\nToken: {token}")
            print(f"\nТеперь запусти: python debug_auth.py explore \"{token}\"")

    elif command == "explore":
        token = sys.argv[2]
        explore_api(token)

    elif command == "all":
        phone = sys.argv[2]
        code = sys.argv[3]
        token = login_phone(phone, code)
        if token:
            explore_api(token)
        else:
            print("Не удалось авторизоваться")

    else:
        print(f"Неизвестная команда: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()