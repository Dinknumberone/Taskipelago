from __future__ import annotations
from typing import TYPE_CHECKING, List
from .prereq_parser import Node, eval_node, _has_or, collect_leaves

if TYPE_CHECKING:
    from . import TaskipelagoWorld


def set_rules(world: "TaskipelagoWorld") -> None:
    player = world.player
    n = len(world._tasks)
    try:
        from RuleBuilder import RuleBuilder
        _set_rules_builder(world, player, n)
    except ImportError:
        _set_rules_lambda(world, player, n)


def _set_rules_builder(world: "TaskipelagoWorld", player: int, n: int) -> None:
    from RuleBuilder import RuleBuilder
    # RuleBuilder doesn't natively support OR, so fall back to lambdas if any
    # OR node exists in the prereqs for this world.
    if any(_has_or(ast) for ast in world._parsed_prereqs + world._parsed_reward_prereqs):
        _set_rules_lambda(world, player, n)
        return

    for i in range(n):
        token_ast = world._parsed_prereqs[i]
        reward_ast = world._parsed_reward_prereqs[i]

        # For pure-AND trees, collect_leaves gives us a flat list.
        req_tokens = [world._token_item_names[j] for j in collect_leaves(token_ast)]
        req_rewards = [world._reward_display_names[j] for j in collect_leaves(reward_ast)]
        all_prereqs = req_tokens + req_rewards

        if all_prereqs:
            complete_loc = world.multiworld.get_location(world._complete_location_names[i], player)
            rb = RuleBuilder(player)
            for name in all_prereqs:
                rb.has(name)
            complete_loc.access_rule = rb.build()

        reward_loc = world.multiworld.get_location(world._reward_location_names[i], player)
        rb = RuleBuilder(player)
        rb.has(world._token_item_names[i])
        for name in all_prereqs:
            rb.has(name)
        reward_loc.access_rule = rb.build()


def _set_rules_lambda(world: "TaskipelagoWorld", player: int, n: int) -> None:
    token_names = world._token_item_names        # indexed by 0-based task
    reward_names = world._reward_display_names   # indexed by 0-based task

    for i in range(n):
        token_ast = world._parsed_prereqs[i]
        reward_ast = world._parsed_reward_prereqs[i]

        if token_ast is not None or reward_ast is not None:
            complete_loc = world.multiworld.get_location(world._complete_location_names[i], player)

            def complete_rule(state, ta=token_ast, ra=reward_ast, p=player,
                              tn=token_names, rn=reward_names) -> bool:
                return eval_node(ta, state, p, tn) and eval_node(ra, state, p, rn)

            complete_loc.access_rule = complete_rule

        reward_loc = world.multiworld.get_location(world._reward_location_names[i], player)
        my_token = world._token_item_names[i]

        def reward_rule(state, mt=my_token, ta=token_ast, ra=reward_ast, p=player,
                        tn=token_names, rn=reward_names) -> bool:
            return (
                state.has(mt, p)
                and eval_node(ta, state, p, tn)
                and eval_node(ra, state, p, rn)
            )

        reward_loc.access_rule = reward_rule