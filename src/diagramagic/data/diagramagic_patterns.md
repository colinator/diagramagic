# diagramagic patterns

## 1) Full-page column layout
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <diag:flex width="680" direction="column" gap="14">
    <diag:flex width="680" padding="12" background-class="card"><text style="font-size:18px">System Overview</text></diag:flex>
    <diag:flex width="680" padding="12" gap="8" background-class="card" direction="column">
      <text style="font-size:14px" diag:wrap="true">This section is laid out with no manual y coordinates.</text>
    </diag:flex>
  </diag:flex>
</diag:diagram>
```

## 2) Card grid via templates
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <diag:template name="card"><diag:flex width="180" padding="10" gap="6" direction="column" background-class="card"><text><diag:slot name="title"/></text><text diag:wrap="true"><diag:slot name="body"/></text></diag:flex></diag:template>
  <diag:flex direction="row" gap="12">
    <diag:instance template="card"><diag:param name="title">A</diag:param><diag:param name="body">First card body text.</diag:param></diag:instance>
    <diag:instance template="card"><diag:param name="title">B</diag:param><diag:param name="body">Second card body text.</diag:param></diag:instance>
  </diag:flex>
</diag:diagram>
```

## 3) Nested flex sections
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <diag:flex width="700" direction="column" gap="12">
    <diag:flex direction="row" gap="12">
      <diag:flex width="220" padding="10" direction="column" gap="6" background-class="lane"><text>Backlog</text><text diag:wrap="true">Gather requirements.</text></diag:flex>
      <diag:flex width="220" padding="10" direction="column" gap="6" background-class="lane"><text>In Progress</text><text diag:wrap="true">Implement renderer.</text></diag:flex>
      <diag:flex width="220" padding="10" direction="column" gap="6" background-class="lane"><text>Done</text><text diag:wrap="true">Publish package.</text></diag:flex>
    </diag:flex>
  </diag:flex>
</diag:diagram>
```

## 4) Embedded sub-diagram with <g transform>
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <diag:flex width="420" padding="12" gap="8" direction="column" background-class="panel">
    <text>Service Detail</text>
    <g transform="scale(0.45)">
      <diag:flex width="760" padding="12" gap="8" direction="column" background-class="card">
        <text style="font-size:18px">Internal Flow</text>
        <text diag:wrap="true">This nested sub-diagram contributes to parent layout bounds.</text>
      </diag:flex>
    </g>
  </diag:flex>
</diag:diagram>
```

## 5) Mixed raw SVG + flex
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#555"/></marker></defs>
  <diag:flex id="left" x="20" y="30" width="180" padding="10" background-class="card"><text>API</text></diag:flex>
  <diag:flex id="right" x="300" y="30" width="180" padding="10" background-class="card"><text>DB</text></diag:flex>
  <line x1="200" y1="50" x2="300" y2="50" stroke="#555" marker-end="url(#arrow)"/>
</diag:diagram>
```
