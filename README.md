# Soul

Soul is a local-first Python CLI autonomous assistant for studying and learning.

Architecture:
  Agent --> Plan --> Tool Use --> Verify --> Repeat --> Resond
                                 |            |
                                 |          Repeat
                                 | 
                                1. MemoryRecall
                                2. MemoryWrite
                                3. WebSearch
                                4. Whatsapp/GatewayTool