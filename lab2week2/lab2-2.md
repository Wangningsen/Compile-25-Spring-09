## 赋值表达式  

```python
    def assignment_expression(self, node: Node, statements: list):
        # week2 assignment
        # Tree‑sitter JavaScript / TypeScript 语法：
        # (assignment_expression
        #     left:  <node>
        #     operator: "="
        #     right: <node>)
        left_node  = node.child_by_field_name("left")  or node.named_children[0]
        right_node = node.child_by_field_name("right") or node.named_children[-1]

        # 只允许 identifier / literal
        if not (self.is_identifier(left_node) or self.is_literal(left_node)):
            return                          # 非简单左值：跳过
        if not (self.is_identifier(right_node) or self.is_literal(right_node)):
            return                          # 非简单右值：跳过

        target = self.read_node_text(left_node)
        value  = self.parse(right_node, statements)    # 调父类解析，保证字符串字面量等被处理

        # 生成中间表示
        stmt = {
            "assign_stmt": {
                "target": target,
                "oprand":  value,
            }
        }
        statements.append(stmt)
        return target        
```

定义了`assignment_expression`方法，用于解析赋值表达式。此处只需要考虑左右值为简单变量或常量即可，无需考虑表达式和数组等等。  
该方法接受两个参数：`node`和`statements`，期中`node`表示当前语法树的节点，代表一个赋值表达式；`statements`是一个用来保存`GIR`解析结果的列表。  
首先，获取赋值语句的左值与右值，分别存在`left_node`和`right_node`中，并验证左值与右值是否满足为标识符或字面量，若非简单值直接跳过。随后，获取目标`target`和值`oprand`，分别对应左值和右值的父类解析。最后，用得到的结果生成中间表示GIR，并返回左值。