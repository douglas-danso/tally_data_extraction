"""Simple API test script."""

import asyncio

import httpx


BASE_URL = "http://localhost:8000"


async def test_health():
    """Test health endpoint."""
    print("\n1. Testing health endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        assert response.status_code == 200


async def test_list_packages():
    """Test public packages listing."""
    print("\n2. Testing packages listing...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/packages")
        print(f"   Status: {response.status_code}")
        data = response.json()
        print(f"   Found {len(data)} packages")
        for pkg in data:
            print(f"   - {pkg['name']}: £{pkg['price_gbp']} ({pkg['credits']} credits)")
        assert response.status_code == 200


async def test_admin_login():
    """Test admin login."""
    print("\n3. Testing admin login...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/admin/login",
            json={"email": "admin@example.com", "password": "admin123"},
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            token = data["access_token"]
            print(f"   ✅ Login successful!")
            print(f"   Token: {token[:50]}...")
            return token
        else:
            print(f"   ❌ Login failed: {response.text}")
            return None


async def test_admin_users(token: str):
    """Test admin users listing."""
    if not token:
        print("\n4. Skipping admin users test (no token)")
        return

    print("\n4. Testing admin users listing...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Found {len(data)} users")
            for user in data:
                print(
                    f"   - {user['email']}: {user['credits']} credits"
                    + (" (unlimited)" if user['is_unlimited'] else "")
                )


async def test_admin_packages(token: str):
    """Test admin packages listing."""
    if not token:
        print("\n5. Skipping admin packages test (no token)")
        return

    print("\n5. Testing admin packages listing...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/admin/packages",
            headers={"Authorization": f"Bearer {token}"},
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Found {len(data)} packages (including inactive)")
            for pkg in data:
                status = "✅ Active" if pkg['is_active'] else "❌ Inactive"
                print(f"   - {pkg['name']}: £{pkg['price_gbp']} ({status})")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("NHS Supporting Information Generator - API Tests")
    print("=" * 60)

    try:
        await test_health()
        await test_list_packages()
        token = await test_admin_login()
        await test_admin_users(token)
        await test_admin_packages(token)

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
