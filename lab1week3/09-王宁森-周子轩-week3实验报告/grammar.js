module.exports = grammar({
    name: 'typescript',
    extras: $ => [
        $.comment,
        /\s/,  // Whitespace
        /[\s\p{Zs}\uFEFF\u2028\u2029\u2060\u200B]/,
    ],
    // precedences: $ => [

    //     ['declaration', 'literal'],

    // ],
    word: $ => $.identifier,
    rules: {
        program: $ => seq(
          optional($.hash_bang_line),
          repeat($.statement),
        ),
    
        hash_bang_line: _ => /#!.*/,

        statement: $ => choice(
            $.declaration,
            $.statement_block,
            $.expression_statement,
            $.if_statement
        ),

        if_statement: $ => prec.right(seq(
            //week3 if语句
            'if',
            field('condition', $.parenthesized_expression),
            field('consequence', $.statement),
            optional(seq(
                'else',
                field('alternative', $.statement)
            ))
        )),
       
        parenthesized_expression: $ => seq(
            //week3 括号表达式,用于if_statement的条件部分
            
            '(',
            $.expression,
            ')'
            
        ),

        variable_declaration: $ => choice(
            // const声明必须初始化
            seq(
                field('kind', 'const'),
                field('name', $.identifier), // 变量名
                optional(field('type', $.type_annotation)), // 可选的类型注解
                seq('=', field('value', $.expression)), // 初始化表达式是必须的
                optional($._semicolon)
            ),
            // let声明初始化表达式是可选的
            seq(
                field('kind', 'let'),
                field('name', $.identifier),
                optional(field('type', $.type_annotation)),
                optional(seq('=', field('value', $.expression))), // 初始化表达式是可选的
                optional($._semicolon)
            )
        ),

       

        number: _ => {
          //week2任务，10、16进制数的正则表达式
          const hex_literal = /0[xX][0-9a-fA-F]+/;
    
          const decimal_digits = /[0-9]+/;
    
          return token(choice(
            hex_literal,
            decimal_digits,
          ));
        },
        expression_statement: $ => seq(
            $.expression,
            optional($._semicolon),
        ),
        expression: $ => choice(
            $.assignment_expression,
            $.identifier,
            $.number
        ),

        assignment_expression: $ => prec.right(seq(
            optional('using'),
            field('left', $.identifier),
            '=',
            field('right', $.expression),
        )),

        declaration: $ => choice(
            $.function_declaration,
            $.variable_declaration,
        ),

        function_declaration: $ => prec.right(seq(
            optional('async'),
            'function',
            field('name', $.identifier),
            $.call_signature,
            field('body', $.statement_block),
            optional($._semicolon),
          )),
        
        call_signature: $ => seq(
            //week2任务，函数的调用签名，包括参数与返回类型
            $.formal_parameters, // 引用 formal_parameters 规则
            $.type_annotation  // 返回类型注释
        ),
        formal_parameters: $ => seq(
            '(',
            //week2
            commaSep(seq(
                field('name', $.identifier),
                field('type', optional($.type_annotation))
            )),
            ')',
        ),
        required_parameter: $ => seq(
            $.identifier,
            field('type', optional($.type_annotation)),
        ),


        type_annotation: $ => seq(
            ':',$.primitive_type,
        ),

        primitive_type: _ => choice(
            'any', 'number','boolean','string','symbol','void','unknown','string','never','object',
        ),
        statement_block: $ => prec.right(seq(
            '{',
            repeat($.statement),
            '}',
            optional($._semicolon),
        )),

          
        comment: $ => choice(
            token(choice(
            seq('//', /.*/),
            seq(
                '/*',
                /[^*]*\*+([^/*][^*]*\*+)*/,
                '/',
            ),
            )),
        ),

        
        
        identifier: $ => /[_a-zA-Z][_a-zA-Z0-9]*/, 
        
        // 分号
        _semicolon: $ => ';',

    }
    
})



function commaSep1(rule) {
    return seq(rule, repeat(seq(',', rule)));
  }
  
  function commaSep(rule) {
    return optional(commaSep1(rule));
  }
  
  function sepBy1(sep, rule) {
    return seq(rule, repeat(seq(sep, rule)));
  }