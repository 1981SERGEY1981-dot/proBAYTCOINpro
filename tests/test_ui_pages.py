def test_login_page_html(client):
    rv = client.get('/login')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert '<form' in html
    assert 'name="username"' in html
    assert 'name="password"' in html
    assert '<button' in html
    assert '<script' in html  

