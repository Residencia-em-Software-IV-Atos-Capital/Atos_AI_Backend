# import pandas as pd
# from flask import Flask, jsonify
# from models import request_models

# app = Flask(__name__)

# def kpi_calculate():
#     try:
#         df = pd.DataFrame(request_models.py)
        
#         df['lucro'] = df['x_axis'] - df['y_axis']
#         total_profit = df['lucro'].sum() 
        
#         return {'Lucro final': float(round(total_profit, 2))}           
#     except FileNotFoundError:
#         return 'Arquivo não encontrado'
#     except Exception as e:
#         return f'Error: Ocorreu um erro {e}'
    
# @app.route('/KPI/PROFIT', methods=['GET'])
# def get_kpi_profit():
#     kpi_data = kpi_calculate()
    
#     return jsonify(kpi_data)

# if __name__ == '__main__':
#     app.run(debug=True)