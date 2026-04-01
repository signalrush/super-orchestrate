def test_ctx_importable():
    from claude_code_orchestrate import ctx
    assert hasattr(ctx, "init")
    assert hasattr(ctx, "put")
    assert hasattr(ctx, "get")
    assert hasattr(ctx, "ls")
    assert hasattr(ctx, "search")
    assert hasattr(ctx, "rm")
    assert callable(ctx.init)


def test_ctx_in_all():
    import claude_code_orchestrate
    assert "ctx" in claude_code_orchestrate.__all__
