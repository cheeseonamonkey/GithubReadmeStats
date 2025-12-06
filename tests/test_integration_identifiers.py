"""Integration tests for code_identifiers endpoint with real GitHub data."""

import pytest
from github_cards.code_identifiers.card import CodeIdentifiersCard


# Target usernames for testing
TEST_USERS = [
    "cheeseonamonkey",
    "brianpetro",
    "shubham0204",
    "hdbham",
    "jackschedel",
]


@pytest.mark.integration
class TestRealGitHubData:
    """Integration tests hitting real GitHub API."""

    def test_fetch_all_users(self):
        """Test that we can fetch data for all target users without errors."""
        for username in TEST_USERS:
            print(f"\n{'='*60}")
            print(f"Testing user: {username}")
            print('='*60)

            card = CodeIdentifiersCard(username, {})
            data = card.fetch_data()

            # Simple smoke test - no strict assertions
            assert data is not None, f"Failed to fetch data for {username}"
            assert 'items' in data, f"Missing 'items' key for {username}"
            assert 'repo_count' in data, f"Missing 'repo_count' key for {username}"
            assert 'file_count' in data, f"Missing 'file_count' key for {username}"

            print(f"✓ {username}: {len(data['items'])} identifiers found")
            print(f"  Repos: {data['repo_count']}, Files: {data['file_count']}")

    def test_quality_of_results(self):
        """Verify extracted identifiers look reasonable (no obvious noise)."""
        for username in TEST_USERS:
            card = CodeIdentifiersCard(username, {})
            data = card.fetch_data()

            if not data['items']:
                print(f"⚠ {username}: No identifiers found")
                continue

            top_item = data['items'][0]

            # Verify structure
            assert 'name' in top_item, f"Missing 'name' in top identifier for {username}"
            assert 'count' in top_item, f"Missing 'count' in top identifier for {username}"
            assert top_item['count'] > 0, f"Invalid count for {username}"

            # Verify basic quality (identifier length)
            name = top_item['name']
            assert len(name) >= 3, f"Top identifier too short for {username}: {name}"

            print(f"✓ {username} top identifier: {name} (count: {top_item['count']})")

    def test_n_parameter(self):
        """Test ?n= parameter works correctly with different values."""
        username = TEST_USERS[0]

        print(f"\n{'='*60}")
        print(f"Testing ?n= parameter with user: {username}")
        print('='*60)

        # Test default (15)
        card = CodeIdentifiersCard(username, {})
        data = card.fetch_data()
        default_count = len(data['items'])
        print(f"✓ Default (no param): {default_count} identifiers")
        assert default_count <= 15, "Default should return <= 15 items"

        # Test custom n=5
        card = CodeIdentifiersCard(username, {'n': ['5']})
        data = card.fetch_data()
        custom_count = len(data['items'])
        print(f"✓ n=5: {custom_count} identifiers")
        assert custom_count <= 5, "n=5 should return <= 5 items"

        # Test max limit (50)
        card = CodeIdentifiersCard(username, {'n': ['100']})
        data = card.fetch_data()
        max_count = len(data['items'])
        print(f"✓ n=100 (capped): {max_count} identifiers")
        assert max_count <= 50, "Should cap at 50 items"

        # Test backwards compatibility with 'count' parameter
        card = CodeIdentifiersCard(username, {'count': ['10']})
        data = card.fetch_data()
        compat_count = len(data['items'])
        print(f"✓ count=10 (backwards compat): {compat_count} identifiers")
        assert compat_count <= 10, "count=10 should return <= 10 items"

    def test_language_coverage(self):
        """Verify we extract from multiple languages."""
        for username in TEST_USERS:
            card = CodeIdentifiersCard(username, {})
            data = card.fetch_data()

            lang_files = data.get('language_files', {})
            if lang_files:
                langs = list(lang_files.keys())
                print(f"✓ {username} languages: {', '.join(langs)}")
            else:
                print(f"⚠ {username}: No language data")

    def test_compare_results(self):
        """Document current extraction results for each user."""
        print(f"\n{'='*60}")
        print("EXTRACTION RESULTS SUMMARY")
        print('='*60)

        for username in TEST_USERS:
            card = CodeIdentifiersCard(username, {})
            data = card.fetch_data()

            print(f"\n{username}")
            print(f"  Repos: {data.get('repo_count', 0)}")
            print(f"  Files scanned: {data.get('file_count', 0)}")

            if data.get('language_files'):
                print(f"  Languages: {', '.join(data['language_files'].keys())}")

            print(f"  Top 15 identifiers:")
            for i, item in enumerate(data['items'][:15], 1):
                langs = ", ".join(item.get('langs', {}).keys())
                print(f"    {i:2}. {item['name']:30} ({item['count']:3}) - {langs}")


if __name__ == "__main__":
    # Allow running this file directly for quick testing
    print("Running integration tests...")
    print("Note: These tests hit the real GitHub API and may be slow.\n")

    test = TestRealGitHubData()

    try:
        print("\n1. Testing all users can be fetched...")
        test.test_fetch_all_users()

        print("\n2. Testing quality of results...")
        test.test_quality_of_results()

        print("\n3. Testing ?n= parameter...")
        test.test_n_parameter()

        print("\n4. Testing language coverage...")
        test.test_language_coverage()

        print("\n5. Comparing results across users...")
        test.test_compare_results()

        print("\n" + "="*60)
        print("✓ All integration tests passed!")
        print("="*60)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
