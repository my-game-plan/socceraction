Hybrid-VAEP
-----------

**Hybrid-VAEP** utilizes a slightly adjusted VAEP formula that enables the model to properly value defensive actions and credit pass receivers.

### Formula
Let's first have a look at the original VAEP-formula to pinpoint the issue.


Original VAEP formula: VAEP(a<sub>i</sub>) = (P<sub>scores</sub>(S<sub>i</sub>) – P<sub>scores</sub>(S<sub>i-1</sub>)) + (P<sub>concedes</sub>(S<sub>i</sub>) – P<sub>concedes</sub>(S<sub>i-1</sub>))

❗ <span style="color: red;">**Information leak:** Pre-action game state includes the result (which also depends on the next action)</span>

Hybrid-VAEP formula: VAEP(a<sub>i</sub>) = (P<sub>scores</sub>(S<sub>i</sub>) – P<sub>scores_resultfree</sub>(S<sub>i-1</sub>)) + (P<sub>concedes</sub>(S<sub>i</sub>) - P<sub>concedes_resultfree</sub>(S<sub>i-1</sub>))

### Motivation
When calculating the probabilities for the pre-action game state, the model already takes into account the result of that action. But the result also depends on the next action so there is actually an information leakage from the post-action to the pre-action game state! For example, consider a defensive interception of a pass. In this example, the result of the intercepted pass will be 'fail' but this is ofcourse because the defender intercepted it. However, because the model already took into account the unsuccessfulness of the pass when calculating the probabilities, the defender won't be properly rewarded for his interception.

Hybrid-VAEP addresses this issue by excluding features describing the result of actions in the pre-action game state. It thus uses different models for the pre-action and post-action game state. The model for the pre-action game state (the 'resultfree' model) is conceptually similar to the Atomic-VAEP model while the model for the post-action game state is identical to the model in Standard-VAEP. Thus, Hybrid-VAEP is born!

By excluding the result from the pre-action gamestate, players can be properly rewarded for defensive actions and players can also be rewarded for receivals (which is also the case in Atomic-VAEP). However, the model still considers the result of your own action, like in Standard-VAEP.
